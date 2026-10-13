"""The decisions.md §1.1 licence gate: from licence evidence to permissions.

Three layers, each usable on its own:

* :func:`derive_permissions` maps one canonical licence to what ResearchBridge
  may do (the §1.1 table plus its 2026-10-13 addendum).
* :func:`decide` turns the licence evidence found in one source document into
  a single :class:`LicenceDecision`, failing closed on missing, prose-only or
  conflicting evidence.
* :func:`decide_figure` applies a figure's or table's own ``<permissions>``
  block over the article decision.

Precedence *across* sources (PMC JSON vs Europe PMC vs JATS vs arXiv) belongs
to the ingestion layer (Phase 2), which can call :func:`decide` per source.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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
            conflicting values, unrecognised licence URIs, or a figure with
            its own permissions but no machine-readable licence.
        reasons: Human-readable explanation, for logs and the review queue.
        inherited: True for a figure or table that has no permissions block
            of its own and so takes the article's decision.
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


def decide(evidence: Sequence[LicenceEvidence]) -> LicenceDecision:
    """Choose one licence from the evidence found in a single source document.

    Rules, all failing closed:

    1. Only machine-readable fields are used (never ``license-p`` prose or
       ``@license-type``; see :attr:`LicenceField.is_machine_readable`), and
       never aggregator fields (:attr:`LicenceField.is_secondary`).
    2. No machine-readable evidence: ``UNKNOWN``, sent to review if any prose
       or licence type exists.
    3. Machine-readable values that normalise to different licence families
       conflict: ``UNKNOWN`` and review. Versions may differ (by/3.0 and by/4.0
       agree), since versions do not change the gate.
    4. A single agreed family wins; the first item in the given order is
       recorded as the source. An unrecognised value is ``UNKNOWN`` and goes
       to review.

    Args:
        evidence: Licence evidence from one source, in precedence order (for
            JATS, :meth:`PermissionsBlock.evidence` order).

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

    normalised = [(item, normalise_licence(item.value)) for item in usable]
    families = {licence.family for _, licence in normalised}

    # Rule 3: disagreement between machine-readable values goes to a human.
    if len(families) > 1:
        listed = "; ".join(f"{item.field.value}={item.value!r}" for item, _ in normalised)
        return _closed([f"conflicting licence values: {listed}"], needs_review=True)

    source, licence = normalised[0]
    # Rule 4: an unrecognised URI or code fails closed but deserves a look.
    if licence.family is LicenceFamily.UNKNOWN:
        return _closed(
            [f"unrecognised licence value {source.value!r} in {source.field.value}"],
            needs_review=True,
            source=source,
        )
    return LicenceDecision(
        licence=licence,
        permissions=derive_permissions(licence),
        source=source,
        needs_review=False,
        reasons=(f"{licence.label} from {source.field.value}",),
    )


def decide_figure(
    article: LicenceDecision, figure_permissions: PermissionsBlock | None
) -> LicenceDecision:
    """Decide the licence of a figure or table from its own permissions block.

    JATS4R: an object reproduced under a different licence carries its own
    ``<permissions>``, which overrides the article licence; objects without
    one inherit the article licence (§1.1 addendum).

    Args:
        article: The article-level decision.
        figure_permissions: The figure's or table's own ``<permissions>``
            block, or None if it has none.

    Returns:
        The article decision marked as inherited when there is no block;
        otherwise a decision from the block's own machine-readable licence,
        failing closed (with review) when the block has none, for example a
        copyright line plus "not covered by the CC-BY licence" prose.
    """
    if figure_permissions is None:
        return LicenceDecision(
            licence=article.licence,
            permissions=article.permissions,
            source=article.source,
            needs_review=article.needs_review,
            reasons=(*article.reasons, "inherited from the article licence"),
            inherited=True,
        )

    decision = decide(figure_permissions.evidence())
    if decision.source is None:
        # A permissions block exists precisely because the object is licensed
        # differently; without a machine-readable licence we cannot know how.
        holders = ", ".join(figure_permissions.copyright_holders) or "unstated"
        return _closed(
            [
                "figure/table has its own permissions block without a "
                f"machine-readable licence (copyright holder: {holders})",
                *decision.reasons,
            ],
            needs_review=True,
        )
    return decision


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
