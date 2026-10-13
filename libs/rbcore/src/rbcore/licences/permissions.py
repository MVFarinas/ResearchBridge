"""The decisions.md §1.1 licence gate: from licence evidence to permissions.

Three layers, each usable on its own:

* :func:`derive_permissions` maps one canonical licence to what ResearchBridge
  may do (the §1.1 table plus its 2026-10-13 addendum).
* :func:`decide` turns the licence evidence found in one source document into
  a single :class:`LicenceDecision`, failing closed on missing, prose-only or
  conflicting evidence.
* :func:`decide_part` applies the ``<permissions>`` blocks attached to one
  part of an article (a figure, table or text block) over the article
  decision.

Precedence *across* sources (PMC JSON vs Europe PMC vs JATS vs arXiv) belongs
to the ingestion layer (Phase 2), which can call :func:`decide` per source.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

from rbcore.licences.model import (
    UNKNOWN_LICENCE,
    Licence,
    LicenceEvidence,
    LicenceFamily,
    LicenceField,
    PermissionsBlock,
)
from rbcore.licences.normalise import normalise_licence


@dataclass(frozen=True, slots=True)
class Permissions:
    """What ResearchBridge may do with a work under a given licence.

    Attributes:
        can_display: The original may be shown in full (feature 2).
        can_rewrite: A plain-English derivative may be published (feature 1).
        output_licence: Licence our rewrite must be released under, or None
            when rewriting is not allowed. ResearchBridge mirrors the source
            licence: required for share-alike, always compliant otherwise.
        non_commercial: Use is restricted to non-commercial purposes; a paid
            tier would have to exclude this work (§1.1 consequences).
        attribution_required: The original authors must be credited.
        share_alike: Derivatives must carry the same licence.
    """

    can_display: bool
    can_rewrite: bool
    output_licence: Licence | None
    non_commercial: bool
    attribution_required: bool
    share_alike: bool


NO_PERMISSIONS = Permissions(
    can_display=False,
    can_rewrite=False,
    output_licence=None,
    non_commercial=False,
    attribution_required=False,
    share_alike=False,
)


def derive_permissions(licence: Licence) -> Permissions:
    """Apply the §1.1 table to one licence.

    | Licence                     | Display | Rewrite |
    |-----------------------------|---------|---------|
    | CC BY, CC BY-SA, CC0, PD    | yes     | yes     |
    | CC BY-NC, CC BY-NC-SA       | yes     | yes (non-commercial) |
    | CC BY-ND, CC BY-NC-ND       | yes     | no      |
    | anything else               | no      | no      |

    "Anything else" covers all rights reserved, PMC ``TDM`` author
    manuscripts, the arXiv non-exclusive licence and unknown licences.

    Args:
        licence: The canonical licence.

    Returns:
        The derived permissions; :data:`NO_PERMISSIONS` for closed licences.
    """
    # Fail closed: only licences that grant public redistribution are displayable.
    if not licence.is_open:
        return NO_PERMISSIONS
    can_rewrite = not licence.no_derivatives
    return Permissions(
        can_display=True,
        can_rewrite=can_rewrite,
        output_licence=licence if can_rewrite else None,
        non_commercial=licence.non_commercial,
        attribution_required=licence.attribution,
        share_alike=licence.share_alike,
    )


@dataclass(frozen=True, slots=True)
class LicenceDecision:
    """The licence chosen for a work (or figure) and what it permits.

    Attributes:
        licence: The canonical licence the decision rests on (``UNKNOWN``
            when the decision failed closed).
        permissions: Permissions derived from ``licence``.
        source: The evidence the licence came from, or None when no usable
            machine-readable evidence existed.
        needs_review: True when a human should look: prose-only licences,
            conflicting values, unrecognised licence URIs, embargo or expiry
            dates, use-scoped evidence, a contradicting ``@license-type``, or
            a part with its own permissions but no machine-readable licence.
            A decision may grant permissions and still need review.
        reasons: Human-readable explanation, for logs and the review queue.
        inherited: True for a part (figure, table, text block) that has no
            permissions block of its own and so takes the article's decision.
    """

    licence: Licence
    permissions: Permissions
    source: LicenceEvidence | None
    needs_review: bool
    reasons: tuple[str, ...]
    inherited: bool = False

    @property
    def source_field(self) -> LicenceField | None:
        """The field the licence was read from, if any."""
        return self.source.field if self.source else None


# @specific-use values that do not narrow a licence to one use ("vor" is the
# version of record itself). Compared lower-cased; None counts as unscoped.
_UNSCOPED_USES = frozenset({"", "vor"})


@dataclass(frozen=True, slots=True)
class _DateCheck:
    """The result of checking licence evidence against its ALI dates.

    Attributes:
        in_force: Evidence that applies today, superseded items removed.
        notes: Informational reasons (superseded licence references).
        review: Reasons a human should look although the licence applies.
        failure: Why no decision can be made today, or None.
    """

    in_force: tuple[LicenceEvidence, ...]
    notes: tuple[str, ...] = ()
    review: tuple[str, ...] = ()
    failure: str | None = None


def decide(evidence: Sequence[LicenceEvidence], *, today: date | None = None) -> LicenceDecision:
    """Choose one licence from the evidence found in a single source document.

    Rules, all failing closed:

    1. Only machine-readable fields are used (never ``license-p`` prose or
       ``@license-type``; see :attr:`LicenceField.is_machine_readable`), and
       never aggregator fields (:attr:`LicenceField.is_secondary`).
    2. No machine-readable evidence: ``UNKNOWN``, sent to review if any prose
       or licence type exists.
    3. NISO ALI dates: a ``start_date`` in the future (an embargo), an
       ``end_date`` in the past, or a date that cannot be parsed means the
       licence is not in force today: ``UNKNOWN`` and review. When several
       dated references are in force, the one with the latest ``start_date``
       supersedes the earlier ones (the ALI pattern for delayed open
       access); undated values always count.
    4. Machine-readable values that normalise to different licence families
       conflict: ``UNKNOWN`` and review. Versions may differ (by/3.0 and by/4.0
       agree), since versions do not change the gate.
    5. A single agreed family wins; the first item in the given order is
       recorded as the source. An unrecognised value is ``UNKNOWN`` and goes
       to review.
    6. The licence stands but ``needs_review`` is set when: every value in
       force is scoped by a ``@specific-use`` other than "vor" (for example
       "textmining") so nothing unscoped agrees; a value carries a future
       ``end_date``; or an ``@license-type`` names a different recognised
       licence family. ``@specific-use`` never widens or narrows the
       permissions by itself. PMC tags its own CC references
       ``specific-use="textmining"``, so a caller holding an unscoped value
       from another field of the same paper (for example the PMC
       ``license_code``) should pass it in the same call: when it agrees,
       no review is needed.

    Args:
        evidence: Licence evidence from one source, in precedence order (for
            JATS, :meth:`PermissionsBlock.evidence` order).
        today: The date to judge ALI dates against; defaults to today in UTC.
            Injectable for tests and for re-checking at a later date.

    Returns:
        The decision.
    """
    usable = [e for e in evidence if e.field.is_machine_readable and not e.field.is_secondary]
    unusable = [e for e in evidence if e not in usable]

    # Rule 2: nothing machine-readable, so nothing automated can approve it.
    if not usable:
        reasons = ["no machine-readable licence"]
        if unusable:
            fields = sorted({e.field.value for e in unusable})
            reasons.append(f"only non-authoritative evidence present ({', '.join(fields)})")
        return _closed(reasons, needs_review=bool(unusable))

    # Rule 3: a licence that is not in force today cannot approve anything.
    dates = _check_dates(usable, today or datetime.now(UTC).date())
    if dates.failure is not None:
        return _closed([dates.failure], needs_review=True)

    normalised = [(item, normalise_licence(item.value)) for item in dates.in_force]
    families = {licence.family for _, licence in normalised}

    # Rule 4: disagreement between machine-readable values goes to a human.
    if len(families) > 1:
        listed = "; ".join(f"{item.field.value}={item.value!r}" for item, _ in normalised)
        return _closed([f"conflicting licence values: {listed}"], needs_review=True)

    source, licence = normalised[0]
    # Rule 5: an unrecognised URI or code fails closed but deserves a look.
    if licence.family is LicenceFamily.UNKNOWN:
        return _closed(
            [f"unrecognised licence value {source.value!r} in {source.field.value}", *dates.notes],
            needs_review=True,
            source=source,
        )

    # Rule 6: signals that do not change the permissions but a human should see.
    review = (
        *dates.review,
        *_scope_review(dates.in_force),
        *_licence_type_review(unusable, licence.family),
    )
    return LicenceDecision(
        licence=licence,
        permissions=derive_permissions(licence),
        source=source,
        needs_review=bool(review),
        reasons=(f"{licence.label} from {source.field.value}", *dates.notes, *review),
    )


def _check_dates(usable: Sequence[LicenceEvidence], today: date) -> _DateCheck:
    """Check machine-readable evidence against its ALI start and end dates.

    Args:
        usable: Machine-readable evidence, in precedence order.
        today: The date to judge against.

    Returns:
        The evidence in force today, or a failure reason.
    """
    starts: dict[LicenceEvidence, date] = {}
    review: list[str] = []
    for item in usable:
        described = f"{item.field.value}={item.value!r}"
        # Any unreadable, future-start or past-end date makes the evidence unusable.
        for label, raw in (("start_date", item.start_date), ("end_date", item.end_date)):
            if raw is None:
                continue
            parsed = _parse_date(raw)
            if parsed is None:
                return _DateCheck((), failure=f"unparsable {label} {raw!r} on {described}")
            if label == "start_date" and parsed > today:
                return _DateCheck(
                    (), failure=f"{described} applies only from {raw} (start_date in the future)"
                )
            if label == "end_date" and parsed < today:
                return _DateCheck((), failure=f"{described} ended on {raw} (end_date has passed)")
            if label == "end_date":
                review.append(f"{described} ends on {raw}")
            else:
                starts[item] = parsed

    # The latest start date in force supersedes earlier dated references.
    latest = max(starts.values(), default=None)
    superseded = [item for item, start in starts.items() if start != latest]
    notes = tuple(
        f"{item.field.value}={item.value!r} (start_date {item.start_date}) superseded by a "
        "later start_date"
        for item in superseded
    )
    in_force = tuple(item for item in usable if item not in superseded)
    return _DateCheck(in_force, notes=notes, review=tuple(review))


def _parse_date(raw: str) -> date | None:
    """Parse an ALI date (ISO 8601 date, or a date-time whose date part is used).

    Args:
        raw: The attribute value.

    Returns:
        The date, or None if it is not ISO 8601.
    """
    text = raw.strip()
    try:
        return date.fromisoformat(text)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _scope_review(in_force: Sequence[LicenceEvidence]) -> tuple[str, ...]:
    """Flag a decision that rests only on use-scoped licence references.

    Args:
        in_force: The machine-readable evidence the decision rests on.

    Returns:
        One reason if every item has a narrowing ``@specific-use``, else none.
    """
    uses = [(item.specific_use or "").strip().lower() for item in in_force]
    if not uses or any(use in _UNSCOPED_USES for use in uses):
        return ()
    listed = ", ".join(sorted(set(uses)))
    return (
        f"every machine-readable licence value is scoped by @specific-use ({listed}) and "
        "no unscoped value agrees",
    )


def _licence_type_review(
    unusable: Sequence[LicenceEvidence], decided: LicenceFamily
) -> tuple[str, ...]:
    """Flag ``@license-type`` values that name a different licence family.

    Args:
        unusable: Evidence the gate does not use (prose, licence types, ...).
        decided: The family the decision rests on.

    Returns:
        One reason per contradicting ``@license-type`` value.
    """
    reasons: list[str] = []
    for item in unusable:
        if item.field is not LicenceField.JATS_LICENSE_TYPE:
            continue
        # Uncontrolled values such as "open-access" normalise to UNKNOWN and say nothing.
        family = normalise_licence(item.value).family
        if family not in {LicenceFamily.UNKNOWN, decided}:
            reasons.append(
                f"@license-type {item.value!r} names {family.value}, contradicting {decided.value}"
            )
    return tuple(reasons)


def decide_part(
    article: LicenceDecision,
    part_permissions: Sequence[PermissionsBlock],
    *,
    today: date | None = None,
) -> LicenceDecision:
    """Decide the licence of one part of an article from its own permissions.

    A part is a figure, a table or a text block (paragraph, quotation, boxed
    text). JATS4R: an object reproduced under a different licence carries its
    own ``<permissions>``, which overrides the article licence; parts without
    one inherit the article licence (§1.1 addendum). The parser collects
    every block that applies to a part (its own, an enclosing ``fig-group``,
    ``disp-quote``, ``boxed-text`` or section, and blocks on its ``graphic``
    or ``media``), see :attr:`rbcore.jats.Figure.permissions` and
    :attr:`rbcore.jats.Paragraph.permissions`.

    Blocks marked :attr:`PermissionsBlock.inner` license a separate object
    nested inside the part (an inline media item, quotation or supplementary
    file), not the part's own text, so they never replace its decision. The
    decision from the covering blocks stands only if every inner block
    allows at least as much (display, rewrite, and no added non-commercial,
    share-alike or attribution condition); otherwise the part fails closed
    with review, because one decision cannot express the mix.

    Args:
        article: The article-level decision.
        part_permissions: Every ``<permissions>`` block that applies to the
            part; empty if it has none.
        today: Passed to :func:`decide` for ALI dates.

    Returns:
        From the covering (non-inner) blocks: the article decision marked as
        inherited when there is none; a decision from the block's own
        machine-readable licence when there is exactly one; otherwise a
        fail-closed decision with review: when several blocks apply
        (choosing one could widen access), or when the single block has no
        machine-readable licence, for example a copyright line plus "not
        covered by the CC-BY licence" prose. Inner blocks then either leave
        that decision unchanged (with a note) or close it with review.
    """
    covering = [block for block in part_permissions if not block.inner]
    inner = [block for block in part_permissions if block.inner]
    decision = _decide_covering(article, covering, today=today)

    # Inner blocks may only narrow: keep the decision if each allows at least as much.
    reasons = list(decision.reasons)
    needs_review = decision.needs_review
    for block in inner:
        label = block.context or "nested object"
        nested = _decide_block(block, today=today)
        if not _allows_at_least(nested.permissions, decision.permissions):
            return _closed(
                [
                    f"{label} inside the part has its own permissions ({nested.licence.label}) "
                    "that allow less than the part's own licence; not choosing one",
                    *nested.reasons,
                ],
                needs_review=True,
            )
        reasons.append(
            f"{label} inside the part has its own licence ({nested.licence.label}); "
            "it does not change the part's decision"
        )
        needs_review = needs_review or nested.needs_review
    return replace(decision, needs_review=needs_review, reasons=tuple(reasons))


def _decide_covering(
    article: LicenceDecision,
    covering: Sequence[PermissionsBlock],
    *,
    today: date | None,
) -> LicenceDecision:
    """Decide a part from the permissions blocks that cover it.

    Args:
        article: The article-level decision.
        covering: The part's non-inner permissions blocks.
        today: Passed to :func:`decide` for ALI dates.

    Returns:
        The inherited article decision, the single block's decision, or a
        fail-closed decision with review when several blocks apply.
    """
    if not covering:
        return LicenceDecision(
            licence=article.licence,
            permissions=article.permissions,
            source=article.source,
            needs_review=article.needs_review,
            reasons=(*article.reasons, "inherited from the article licence"),
            inherited=True,
        )

    # Never pick one of several blocks: the most permissive might be the wrong one.
    if len(covering) > 1:
        contexts = ", ".join(block.context or "unknown" for block in covering)
        return _closed(
            [f"{len(covering)} permissions blocks apply ({contexts}); not choosing one"],
            needs_review=True,
        )
    return _decide_block(covering[0], today=today)


def _decide_block(block: PermissionsBlock, *, today: date | None) -> LicenceDecision:
    """Decide the licence stated by one part-level permissions block.

    Args:
        block: The block.
        today: Passed to :func:`decide` for ALI dates.

    Returns:
        The block's decision; fail-closed with review when it has no
        machine-readable licence.
    """
    evidence = block.evidence()
    if not any(item.field.is_machine_readable for item in evidence):
        # A permissions block exists precisely because the object is licensed
        # differently; without a machine-readable licence we cannot know how.
        holders = ", ".join(block.copyright_holders) or "unstated"
        return _closed(
            [
                f"{block.context or 'part'} has its own permissions block without a "
                f"machine-readable licence (copyright holder: {holders})",
                *decide(evidence, today=today).reasons,
            ],
            needs_review=True,
        )
    return decide(evidence, today=today)


def _allows_at_least(nested: Permissions, part: Permissions) -> bool:
    """Whether a nested object's permissions cover everything the part allows.

    Args:
        nested: Permissions of an object nested inside the part.
        part: Permissions decided for the part itself.

    Returns:
        True if every use ``part`` grants is also granted by ``nested``
        without a condition ``part`` lacks (non-commercial, attribution, or
        share-alike under a different licence family).
    """
    # Nothing granted means nothing to narrow.
    if not part.can_display:
        return True
    if not nested.can_display or (part.can_rewrite and not nested.can_rewrite):
        return False
    if (nested.non_commercial and not part.non_commercial) or (
        nested.attribution_required and not part.attribution_required
    ):
        return False
    # A rewrite released under the part's licence must also satisfy a nested share-alike.
    if part.can_rewrite and nested.share_alike:
        ours, theirs = part.output_licence, nested.output_licence
        return ours is not None and theirs is not None and ours.family is theirs.family
    return True


def _closed(
    reasons: Sequence[str], *, needs_review: bool, source: LicenceEvidence | None = None
) -> LicenceDecision:
    """Build a fail-closed decision (no display, no rewrite).

    Args:
        reasons: Why the decision failed closed.
        needs_review: Whether a human should review the work.
        source: The evidence examined, if one item was decisive.

    Returns:
        A decision with :data:`NO_PERMISSIONS` and an ``UNKNOWN`` licence.
    """
    return LicenceDecision(
        licence=UNKNOWN_LICENCE,
        permissions=NO_PERMISSIONS,
        source=source,
        needs_review=needs_review,
        reasons=tuple(reasons),
    )
