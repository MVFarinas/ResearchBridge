"""Compute, persist and recompute licence decisions for a paper version and its parts.

:func:`evaluate_version` is the only code that writes gate decisions. It runs
whenever a version's licence records change (ingestion, re-checks, a resolved
review) and can be re-run at any time: it is a pure function of the stored
records, the stored review resolutions and today's date.

Flow for one version:

1. Rebuild the article-level evidence from the active licence records (PMC
   JSON code, the article's JATS permissions block, ...).
2. :func:`rb_backend.corpus.precedence.resolve_licence` decides it across
   sources.
3. Extra review triggers: ``<permissions>`` blocks the parser could not
   attach to anything, and full text that failed to parse.
4. Anything that needs review is settled against the review queue: a
   resolution for the *same* evidence applies; otherwise an open review is
   kept or created and the version fails closed.
5. Each figure, table and paragraph is decided with
   :func:`rbcore.licences.decide_part` over the version's effective decision,
   and settled the same way.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from rb_backend.corpus.blocks import block_from_rows, evidence_dict, evidence_summary
from rb_backend.corpus.models import (
    BlockScope,
    ContentState,
    Figure,
    GateStatus,
    LicenceReview,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
    ReviewScope,
    ReviewStatus,
)
from rb_backend.corpus.models.gated import GATE_FIELDS, GatedPermissions
from rb_backend.corpus.precedence import DEFINITE_REFUSALS, proposed_licence, resolve_licence
from rbcore.licences import (
    NO_PERMISSIONS,
    UNKNOWN_LICENCE,
    Licence,
    LicenceDecision,
    LicenceEvidence,
    LicenceFamily,
    Permissions,
    PermissionsBlock,
    decide_part,
    derive_permissions,
)


@dataclass(frozen=True, slots=True)
class Outcome:
    """The effective gate result for one version or part.

    Attributes:
        status: The gate status.
        licence: The decided (or proposed) licence.
        permissions: The permissions to store if approved.
        source: Where the decision came from.
        reasons: Human-readable reasons.
    """

    status: GateStatus
    licence: Licence
    permissions: Permissions
    source: str
    reasons: list[str]

    def apply_to(self, row: GatedPermissions, now: datetime) -> None:
        """Store this outcome on a gated row (without saving it).

        Args:
            row: The version, figure or paragraph.
            now: The decision time.
        """
        row.set_decision(
            status=self.status,
            licence=self.licence,
            permissions=self.permissions,
            source=self.source,
            reasons=self.reasons,
            decided_at=now,
        )


def evaluate_version(
    version: PaperVersion, *, today: date | None = None, now: datetime | None = None
) -> GateStatus:
    """Recompute and store the licence decision of a version and all its parts.

    Args:
        version: The version (its stored records are re-read).
        today: Date for NISO ALI licence dates (default: today, UTC).
        now: Timestamp to record (default: now).

    Returns:
        The version's new gate status.
    """
    now = now or timezone.now()
    today = today or now.astimezone(UTC).date()
    with transaction.atomic():
        # Lock the version so two evaluations of it never interleave.
        locked = PaperVersion.objects.select_for_update().get(pk=version.pk)
        blocks = _active_blocks(locked)
        outcome = _version_outcome(locked, blocks, today=today, now=now)
        outcome.apply_to(locked, now)
        locked.save(update_fields=[*GATE_FIELDS, "updated_at"])
        _evaluate_parts(locked, outcome, blocks, today=today, now=now)
    # Keep the caller's instance in step with what was stored.
    version.refresh_from_db()
    return outcome.status


def article_evidence(
    version: PaperVersion, blocks: dict[tuple[str, int | None], list[PermissionsBlock]]
) -> list[LicenceEvidence]:
    """Rebuild the article-level licence evidence from the stored records.

    Args:
        version: The version.
        blocks: The version's active blocks, as returned by
            :func:`_active_blocks`.

    Returns:
        Evidence from non-JATS sources (in stored order) followed by the
        article block's JATS evidence (in rbcore order). Precedence sorting is
        left to :func:`rb_backend.corpus.precedence.resolve_licence`.
    """
    records = version.licence_records.active().filter(block__isnull=True).order_by("position", "pk")
    evidence = [record.as_evidence() for record in records]
    for block in blocks.get((BlockScope.ARTICLE, None), []):
        evidence.extend(block.evidence())
    return evidence


def _active_blocks(
    version: PaperVersion,
) -> dict[tuple[str, int | None], list[PermissionsBlock]]:
    """Load and rebuild every active permissions block of a version.

    Args:
        version: The version.

    Returns:
        Blocks keyed by ``(scope, part primary key)``; article and unattached
        blocks use ``None`` as the part key. Each list is in stored order.
    """
    rows = (
        PermissionsBlockRecord.objects.active()
        .filter(version=version)
        .prefetch_related("records")
        .order_by("scope", "part_stable_id", "position", "pk")
    )
    grouped: dict[tuple[str, int | None], list[PermissionsBlock]] = defaultdict(list)
    for row in rows:
        part_key = row.figure_id if row.scope == BlockScope.FIGURE else row.paragraph_id
        grouped[(row.scope, part_key)].append(block_from_rows(row, list(row.records.all())))
    return grouped


def _version_outcome(
    version: PaperVersion,
    blocks: dict[tuple[str, int | None], list[PermissionsBlock]],
    *,
    today: date,
    now: datetime,
) -> Outcome:
    """Decide a version: precedence, extra review triggers, review queue.

    Args:
        version: The locked version.
        blocks: Its active blocks.
        today: Date for licence dates.
        now: Decision time.

    Returns:
        The version's outcome.
    """
    evidence = article_evidence(version, blocks)
    decision = resolve_licence(evidence, today=today)
    refused = decision.licence.family in DEFINITE_REFUSALS and not decision.needs_review
    reasons = list(decision.reasons)
    needs_review = decision.needs_review
    snapshot: list[dict[str, object]] = [{**evidence_dict(item)} for item in evidence]

    # Blocks the parser could not attach mean part of the paper is licensed
    # differently in a way the stored model cannot express.
    unattached = blocks.get((BlockScope.UNATTACHED, None), [])
    if unattached and not refused:
        needs_review = True
        contexts = ", ".join(sorted({b.context or "unknown" for b in unattached}))
        reasons.append(
            f"{len(unattached)} permissions block(s) attached to content the parser does not "
            f"model ({contexts})"
        )
        snapshot.extend({"unattached_block": evidence_summary(b)} for b in unattached)

    # Full text that failed to parse could hide part-level restrictions.
    if version.content_state == ContentState.FAILED and not refused:
        needs_review = True
        reasons.append(f"full text could not be fetched or parsed: {version.content_error}")
        snapshot.append({"content_error": version.content_error})

    outcome = _settle(
        version,
        ReviewScope.VERSION,
        None,
        decision,
        needs_review=needs_review,
        reasons=reasons,
        snapshot=snapshot,
        proposal=decision.licence
        if decision.licence.family is not LicenceFamily.UNKNOWN
        else proposed_licence(evidence),
        now=now,
    )

    # A licence that allows display still waits for the full text to be parsed.
    if outcome.status == GateStatus.APPROVED and version.content_state != ContentState.PARSED:
        return Outcome(
            GateStatus.PENDING,
            outcome.licence,
            NO_PERMISSIONS,
            outcome.source,
            [*outcome.reasons, "full text not parsed yet"],
        )
    return outcome


def _evaluate_parts(
    version: PaperVersion,
    article: Outcome,
    blocks: dict[tuple[str, int | None], list[PermissionsBlock]],
    *,
    today: date,
    now: datetime,
) -> None:
    """Decide every figure, table and paragraph of a version and store the results.

    Args:
        version: The locked version.
        article: The version's outcome.
        blocks: Its active blocks.
        today: Date for licence dates.
        now: Decision time.
    """
    # Parts only get their own decisions (and reviews) once the article is approved.
    article_decision = (
        LicenceDecision(
            licence=article.licence,
            permissions=article.permissions,
            source=None,
            needs_review=False,
            reasons=tuple(article.reasons),
        )
        if article.status == GateStatus.APPROVED
        else None
    )

    _decide_parts(
        list(Figure.objects.filter(version=version).order_by("position")),
        ReviewScope.FIGURE,
        version,
        article,
        article_decision,
        blocks,
        today=today,
        now=now,
    )
    _decide_parts(
        list(Paragraph.objects.filter(version=version).order_by("position")),
        ReviewScope.PARAGRAPH,
        version,
        article,
        article_decision,
        blocks,
        today=today,
        now=now,
    )


def _decide_parts[P: (Figure, Paragraph)](
    parts: list[P],
    scope: ReviewScope,
    version: PaperVersion,
    article: Outcome,
    article_decision: LicenceDecision | None,
    blocks: dict[tuple[str, int | None], list[PermissionsBlock]],
    *,
    today: date,
    now: datetime,
) -> None:
    """Decide and store every part of one kind (figures, or paragraphs).

    Args:
        parts: The version's figures or paragraphs.
        scope: The matching review scope.
        version: The locked version.
        article: The version's outcome.
        article_decision: The version's rbcore decision, or None if not approved.
        blocks: The version's active blocks.
        today: Date for licence dates.
        now: Decision time.
    """
    # Close open reviews for parts that no longer have blocks (or a decision);
    # review scope values equal the foreign-key names ("figure", "paragraph").
    with_blocks = {pk for (s, pk) in blocks if s == scope.value and pk is not None}
    stale = LicenceReview.objects.filter(version=version, scope=scope, status=ReviewStatus.OPEN)
    if article_decision is not None:
        stale = stale.exclude(**{f"{scope.value}__in": with_blocks})
    stale.update(status=ReviewStatus.SUPERSEDED, updated_at=now)

    for part in parts:
        _part_outcome(
            version, part, scope, article, article_decision, blocks, today=today, now=now
        ).apply_to(part, now)
    # Store all decisions of this kind in one batch.
    if parts:
        type(parts[0]).objects.bulk_update(parts, list(GATE_FIELDS), batch_size=500)


def _part_outcome(
    version: PaperVersion,
    part: Figure | Paragraph,
    scope: ReviewScope,
    article: Outcome,
    article_decision: LicenceDecision | None,
    blocks: dict[tuple[str, int | None], list[PermissionsBlock]],
    *,
    today: date,
    now: datetime,
) -> Outcome:
    """Decide one figure, table or paragraph.

    Args:
        version: The version.
        part: The part.
        scope: Figure or paragraph scope.
        article: The version's outcome.
        article_decision: The version's decision as rbcore sees it, or None
            when the version is not approved.
        blocks: The version's active blocks.
        today: Date for licence dates.
        now: Decision time.

    Returns:
        The part's outcome.
    """
    if article_decision is None:
        return Outcome(
            GateStatus.PENDING,
            article.licence,
            NO_PERMISSIONS,
            "",
            [f"waiting on the article licence (status: {article.status})"],
        )

    part_blocks = blocks.get((scope.value, part.pk), [])
    # Most parts have no permissions of their own and simply inherit.
    if not part_blocks:
        return Outcome(
            GateStatus.APPROVED,
            article.licence,
            article.permissions,
            f"inherited:{article.source}" if article.source else "inherited",
            ["inherited from the article licence"],
        )

    decision = decide_part(article_decision, part_blocks, today=today)
    return _settle(
        version,
        scope,
        part,
        decision,
        needs_review=decision.needs_review,
        reasons=list(decision.reasons),
        snapshot=[evidence_summary(block) for block in part_blocks],
        proposal=decision.licence
        if decision.licence.family is not LicenceFamily.UNKNOWN
        else proposed_licence([item for block in part_blocks for item in block.evidence()]),
        now=now,
    )


def _settle(
    version: PaperVersion,
    scope: ReviewScope,
    part: Figure | Paragraph | None,
    decision: LicenceDecision,
    *,
    needs_review: bool,
    reasons: list[str],
    snapshot: Sequence[dict[str, object]],
    proposal: Licence,
    now: datetime,
) -> Outcome:
    """Turn a decision into an outcome, consulting and updating the review queue.

    Args:
        version: The version.
        scope: Review scope.
        part: The figure or paragraph, for part scopes.
        decision: The automated decision.
        needs_review: Whether a human must decide.
        reasons: Reasons (the decision's plus any extra triggers).
        snapshot: Evidence snapshot for the reviewer.
        proposal: Licence to suggest to the reviewer.
        now: Decision time.

    Returns:
        Approved or rejected from the automated decision when no review is
        needed; the resolution of a matching resolved review; otherwise
        "review" with no permissions and an open review in the queue.
    """
    reviews = _reviews_for(version, scope, part)

    # No review needed: the automated decision stands; open reviews are moot.
    if not needs_review:
        reviews.filter(status=ReviewStatus.OPEN).update(
            status=ReviewStatus.SUPERSEDED, updated_at=now
        )
        status = GateStatus.APPROVED if decision.permissions.can_display else GateStatus.REJECTED
        source = decision.source_field.value if decision.source_field else ""
        return Outcome(status, decision.licence, decision.permissions, source, reasons)

    # A human already resolved exactly this evidence: apply their answer.
    fingerprint = _fingerprint(scope, part, snapshot, reasons)
    resolved = (
        reviews.filter(
            evidence_fingerprint=fingerprint,
            status__in=[ReviewStatus.APPROVED, ReviewStatus.REJECTED],
        )
        .order_by("-resolved_at", "-pk")
        .first()
    )
    if resolved is not None:
        reviews.filter(status=ReviewStatus.OPEN).update(
            status=ReviewStatus.SUPERSEDED, updated_at=now
        )
        return _resolved_outcome(resolved, reasons)

    # Otherwise keep (or open) one review for this evidence and fail closed.
    reviews.filter(status=ReviewStatus.OPEN).exclude(evidence_fingerprint=fingerprint).update(
        status=ReviewStatus.SUPERSEDED, updated_at=now
    )
    review = reviews.filter(status=ReviewStatus.OPEN).first()
    if review is None:
        review = LicenceReview.objects.create(
            version=version,
            scope=scope,
            figure=part if isinstance(part, Figure) else None,
            paragraph=part if isinstance(part, Paragraph) else None,
            reasons=reasons,
            evidence=list(snapshot),
            evidence_fingerprint=fingerprint,
            proposed_family=proposal.family.value
            if proposal.family is not LicenceFamily.UNKNOWN
            else "",
            proposed_version=proposal.version or "",
            proposed_jurisdiction=proposal.jurisdiction or "",
        )
    return Outcome(
        GateStatus.REVIEW,
        proposal if proposal.family is not LicenceFamily.UNKNOWN else UNKNOWN_LICENCE,
        NO_PERMISSIONS,
        "",
        [*reasons, f"awaiting licence review #{review.pk}"],
    )


def _resolved_outcome(review: LicenceReview, reasons: list[str]) -> Outcome:
    """The outcome a resolved review imposes.

    Args:
        review: An approved or rejected review.
        reasons: The automated reasons, kept for the record.

    Returns:
        Approved with the reviewer's licence (or rejected, if that licence
        does not allow display), or rejected.
    """
    source = f"licence-review:{review.pk}"
    if review.status == ReviewStatus.REJECTED:
        return Outcome(
            GateStatus.REJECTED,
            UNKNOWN_LICENCE,
            NO_PERMISSIONS,
            source,
            [*reasons, f"rejected in licence review #{review.pk}"],
        )
    licence = Licence(
        LicenceFamily(review.resolved_family),
        review.resolved_version or None,
        review.resolved_jurisdiction or None,
    )
    permissions = derive_permissions(licence)
    status = GateStatus.APPROVED if permissions.can_display else GateStatus.REJECTED
    return Outcome(
        status,
        licence,
        permissions,
        source,
        [*reasons, f"resolved as {licence.label} in licence review #{review.pk}"],
    )


def _reviews_for(
    version: PaperVersion, scope: ReviewScope, part: Figure | Paragraph | None
) -> QuerySet[LicenceReview]:
    """Reviews of one version scope (and part).

    Args:
        version: The version.
        scope: Review scope.
        part: The figure or paragraph, for part scopes.

    Returns:
        A queryset of the matching reviews.
    """
    condition = Q(version=version, scope=scope)
    if isinstance(part, Figure):
        condition &= Q(figure=part)
    elif isinstance(part, Paragraph):
        condition &= Q(paragraph=part)
    return LicenceReview.objects.filter(condition)


def _fingerprint(
    scope: ReviewScope,
    part: Figure | Paragraph | None,
    snapshot: Sequence[dict[str, object]],
    reasons: Sequence[str],
) -> str:
    """Hash the exact situation a review is about.

    Args:
        scope: Review scope.
        part: The figure or paragraph, if any.
        snapshot: The evidence snapshot.
        reasons: The automated reasons.

    Returns:
        A SHA-256 hex digest over scope, part, evidence and reasons.
    """
    payload = {
        "scope": scope.value,
        "part": part.stable_id if part is not None else None,
        "evidence": list(snapshot),
        "reasons": list(reasons),
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
