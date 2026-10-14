"""Precedence across licence sources (decisions.md §1.1 addendum; Plan.md Phase 2).

rbcore's :func:`rbcore.licences.decide` judges evidence from one source. A
paper version can have evidence from several: the PMC JSON ``license_code``,
the JATS XML of the same article, and later Europe PMC, arXiv or bioRxiv. This
module combines them, in this order of precedence:

1. PMC ``license_code`` (PMC Cloud Service JSON)
2. Europe PMC ``license`` (REST API)
3. JATS (``ali:license_ref``, ``license/@xlink:href``; prose and
   ``@license-type`` only ever trigger review)
4. arXiv OAI-PMH ``<license>``
5. bioRxiv / medRxiv API ``license``

Crossref and OpenAlex fields are secondary signals: recorded, never the gate.

Rules, all failing closed:

* **The highest-precedence source decides refusals outright.** If the
  highest-precedence source with machine-readable evidence says ``TDM``
  (PMC author manuscript), the arXiv non-exclusive licence or "no reuse",
  the version is rejected without review, whatever lower sources say.
* **Otherwise every source must agree.** All evidence is judged together by
  :func:`rbcore.licences.decide`, ordered by precedence, so the recorded
  source is the highest-precedence one and any disagreement between sources
  (different licence families) fails closed and goes to review rather than
  silently taking the most permissive value. An agreeing unscoped PMC code
  also clears the review flag that PMC's ``specific-use="textmining"`` JATS
  references raise on their own.
* Prose-only evidence, unrecognised values and unparseable dates go to
  review (rbcore's rules).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date

from rbcore.licences import (
    UNKNOWN_LICENCE,
    Licence,
    LicenceDecision,
    LicenceEvidence,
    LicenceFamily,
    LicenceField,
    decide,
    derive_permissions,
    normalise_licence,
)

# Rank of each field: lower wins. JATS fields share one rank (one source).
SOURCE_PRECEDENCE: dict[LicenceField, int] = {
    LicenceField.PMC_LICENSE_CODE: 0,
    LicenceField.EUROPE_PMC_LICENSE: 1,
    LicenceField.JATS_ALI_LICENSE_REF: 2,
    LicenceField.JATS_LICENSE_XLINK_HREF: 2,
    LicenceField.JATS_LICENSE_TYPE: 2,
    LicenceField.JATS_LICENSE_P: 2,
    LicenceField.ARXIV_OAI_LICENSE: 3,
    LicenceField.BIORXIV_LICENSE: 4,
    LicenceField.CROSSREF_LICENSE: 5,
    LicenceField.OPENALEX_LICENSE: 5,
}

# Licences that refuse both display and rewriting by definition (never review).
DEFINITE_REFUSALS: frozenset[LicenceFamily] = frozenset(
    {LicenceFamily.TDM, LicenceFamily.ARXIV_NONEXCLUSIVE, LicenceFamily.ALL_RIGHTS_RESERVED}
)


def precedence_of(field: LicenceField) -> int:
    """Return a field's precedence rank (lower wins).

    Args:
        field: The licence field.

    Returns:
        The rank from :data:`SOURCE_PRECEDENCE`.
    """
    return SOURCE_PRECEDENCE[field]


def is_gate_evidence(item: LicenceEvidence) -> bool:
    """Whether a value may decide the gate (machine-readable and not secondary).

    Args:
        item: One piece of evidence.

    Returns:
        True for authoritative machine-readable fields.
    """
    return item.field.is_machine_readable and not item.field.is_secondary


def order_by_precedence(evidence: Sequence[LicenceEvidence]) -> list[LicenceEvidence]:
    """Sort evidence by source precedence, keeping each source's own order.

    Args:
        evidence: Evidence from any number of sources.

    Returns:
        A new list, highest precedence first (the sort is stable).
    """
    return sorted(evidence, key=lambda item: precedence_of(item.field))


def proposed_licence(evidence: Sequence[LicenceEvidence]) -> Licence:
    """The licence a reviewer is offered: the highest-precedence recognised value.

    It is only a suggestion for the review queue; it is never applied
    without a human.

    Args:
        evidence: Evidence from any number of sources.

    Returns:
        The first recognised machine-readable licence in precedence order, or
        ``UNKNOWN``.
    """
    for item in order_by_precedence(evidence):
        if is_gate_evidence(item):
            licence = normalise_licence(item.value)
            if licence.family is not LicenceFamily.UNKNOWN:
                return licence
    return UNKNOWN_LICENCE


def resolve_licence(
    evidence: Sequence[LicenceEvidence], *, today: date | None = None
) -> LicenceDecision:
    """Decide a version's licence from the evidence of every source.

    Args:
        evidence: Article-level evidence from all sources, each source's
            items in its own order (for JATS, ``PermissionsBlock.evidence()``
            order).
        today: Date for NISO ALI start and end dates (default: today, UTC).

    Returns:
        The decision. ``source`` is the highest-precedence evidence it rests
        on. A refusal by the highest-precedence source has
        ``needs_review=False``.
    """
    ordered = order_by_precedence(evidence)
    gate = [item for item in ordered if is_gate_evidence(item)]

    # The top source's definite refusal ends the matter; lower sources cannot widen it.
    if gate:
        top_rank = precedence_of(gate[0].field)
        top = decide(
            [item for item in ordered if precedence_of(item.field) == top_rank], today=today
        )
        if top.licence.family in DEFINITE_REFUSALS and not top.needs_review:
            lower = sorted(
                {item.field.value for item in gate if precedence_of(item.field) > top_rank}
            )
            note = (
                f"refused by the highest-precedence source; lower sources not consulted "
                f"({', '.join(lower)})"
                if lower
                else "refused by the highest-precedence source"
            )
            return replace(top, reasons=(*top.reasons, note))

    # Otherwise all sources are judged together: agreement grants, disagreement reviews.
    return _with_version(decide(ordered, today=today), gate)


def _with_version(decision: LicenceDecision, gate: Sequence[LicenceEvidence]) -> LicenceDecision:
    """Fill in a licence version from agreeing evidence when the decider has none.

    PMC codes such as "CC BY" carry no version, while the JATS of the same
    article usually does ("by/4.0"). Sources that reached a decision agree on
    the family, so borrowing the version changes no permission; it only lets
    attribution name the exact licence.

    Args:
        decision: The combined decision.
        gate: Gate evidence in precedence order.

    Returns:
        The decision with a version (and port) from the highest-precedence
        agreeing value that has one, or the decision unchanged.
    """
    licence = decision.licence
    if licence.version is not None or licence.family is LicenceFamily.UNKNOWN:
        return decision
    for item in gate:
        candidate = normalise_licence(item.value)
        if candidate.family is licence.family and candidate.version is not None:
            return replace(
                decision,
                licence=candidate,
                permissions=derive_permissions(candidate),
                reasons=(*decision.reasons, f"version {candidate.version} from {item.field.value}"),
            )
    return decision
