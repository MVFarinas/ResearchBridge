"""Precedence across licence sources (pure; no database)."""

from __future__ import annotations

from datetime import date

import pytest

from rb_backend.corpus.precedence import (
    SOURCE_PRECEDENCE,
    order_by_precedence,
    proposed_licence,
    resolve_licence,
)
from rbcore.licences import LicenceEvidence, LicenceFamily, LicenceField

F = LicenceField
TODAY = date(2026, 10, 13)
CC_BY_4 = "http://creativecommons.org/licenses/by/4.0/"


def ev(field: LicenceField, value: str, **kwargs: str) -> LicenceEvidence:
    """Shorthand for one piece of synthetic evidence."""
    return LicenceEvidence(field, value, **kwargs)


def test_precedence_order_is_the_documented_one() -> None:
    """PMC code, then Europe PMC, then JATS, then arXiv, then bioRxiv; aggregators last."""
    ranks = [
        SOURCE_PRECEDENCE[f]
        for f in (
            F.PMC_LICENSE_CODE,
            F.EUROPE_PMC_LICENSE,
            F.JATS_ALI_LICENSE_REF,
            F.ARXIV_OAI_LICENSE,
            F.BIORXIV_LICENSE,
            F.OPENALEX_LICENSE,
        )
    ]
    assert ranks == sorted(ranks)
    assert len(set(ranks)) == len(ranks)
    assert set(SOURCE_PRECEDENCE) == set(LicenceField)


def test_order_by_precedence_is_stable_within_a_source() -> None:
    """Items of one source keep their order; sources are sorted by rank."""
    items = [
        ev(F.JATS_LICENSE_XLINK_HREF, "b"),
        ev(F.PMC_LICENSE_CODE, "CC BY"),
        ev(F.JATS_ALI_LICENSE_REF, "a"),
    ]
    assert [i.value for i in order_by_precedence(items)] == ["CC BY", "b", "a"]


def test_agreeing_pmc_code_and_jats_approve_without_review() -> None:
    """The PMC code clears the review flag PMC's textmining-scoped JATS refs raise alone."""
    decision = resolve_licence(
        [
            ev(F.JATS_ALI_LICENSE_REF, CC_BY_4, specific_use="textmining"),
            ev(F.PMC_LICENSE_CODE, "CC BY"),
        ],
        today=TODAY,
    )
    assert decision.licence.family is LicenceFamily.CC_BY
    assert decision.permissions.can_rewrite
    assert not decision.needs_review
    assert decision.source_field is F.PMC_LICENSE_CODE


def test_version_is_borrowed_from_agreeing_jats() -> None:
    """A versionless PMC code takes the version from the JATS of the same paper."""
    decision = resolve_licence(
        [ev(F.PMC_LICENSE_CODE, "CC BY"), ev(F.JATS_ALI_LICENSE_REF, CC_BY_4)], today=TODAY
    )
    assert decision.licence.version == "4.0"
    assert decision.permissions.output_licence is not None
    assert decision.permissions.output_licence.version == "4.0"
    assert any("version 4.0 from jats:ali:license_ref" in r for r in decision.reasons)


def test_tdm_at_the_top_is_rejected_outright_even_if_jats_says_cc_by() -> None:
    """A refusal by the highest-precedence source is final and needs no review."""
    decision = resolve_licence(
        [ev(F.PMC_LICENSE_CODE, "TDM"), ev(F.JATS_ALI_LICENSE_REF, CC_BY_4)], today=TODAY
    )
    assert decision.licence.family is LicenceFamily.TDM
    assert not decision.permissions.can_display
    assert not decision.needs_review
    assert "lower sources not consulted" in decision.reasons[-1]


@pytest.mark.parametrize(
    ("field", "value", "family"),
    [
        (
            F.ARXIV_OAI_LICENSE,
            "http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
            LicenceFamily.ARXIV_NONEXCLUSIVE,
        ),
        (F.BIORXIV_LICENSE, "cc_no", LicenceFamily.ALL_RIGHTS_RESERVED),
    ],
)
def test_other_definite_refusals(field: LicenceField, value: str, family: LicenceFamily) -> None:
    """The arXiv non-exclusive licence and bioRxiv "no reuse" are refused without review."""
    decision = resolve_licence([ev(field, value)], today=TODAY)
    assert decision.licence.family is family
    assert not decision.permissions.can_display
    assert not decision.needs_review


def test_lower_source_disagreeing_with_a_permissive_top_goes_to_review() -> None:
    """Disagreement fails closed: never silently take either value."""
    decision = resolve_licence(
        [ev(F.PMC_LICENSE_CODE, "CC BY"), ev(F.EUROPE_PMC_LICENSE, "cc by-nd")], today=TODAY
    )
    assert decision.needs_review
    assert not decision.permissions.can_display
    assert "conflicting" in decision.reasons[0]


def test_lower_source_refusal_under_a_permissive_top_goes_to_review() -> None:
    """A lower source that refuses cannot be overridden automatically either."""
    decision = resolve_licence(
        [
            ev(F.PMC_LICENSE_CODE, "CC BY"),
            ev(F.ARXIV_OAI_LICENSE, "http://arxiv.org/licenses/nonexclusive-distrib/1.0/"),
        ],
        today=TODAY,
    )
    assert decision.needs_review
    assert not decision.permissions.can_display


def test_jats_decides_when_no_higher_source_exists() -> None:
    """Without a PMC code, the JATS licence is the gate (an unscoped xlink:href)."""
    decision = resolve_licence([ev(F.JATS_LICENSE_XLINK_HREF, CC_BY_4)], today=TODAY)
    assert decision.licence.family is LicenceFamily.CC_BY
    assert not decision.needs_review
    assert decision.source_field is F.JATS_LICENSE_XLINK_HREF


def test_prose_only_goes_to_review() -> None:
    """License-p prose is never used to approve anything."""
    decision = resolve_licence(
        [ev(F.JATS_LICENSE_P, "This article is distributed under the terms of CC BY.")],
        today=TODAY,
    )
    assert decision.needs_review
    assert not decision.permissions.can_display


def test_prose_beside_a_machine_readable_top_source_is_ignored() -> None:
    """Display prose does not block a decision made from a machine-readable field."""
    decision = resolve_licence(
        [ev(F.PMC_LICENSE_CODE, "CC BY"), ev(F.JATS_LICENSE_P, "Free to read and reuse.")],
        today=TODAY,
    )
    assert decision.permissions.can_display
    assert not decision.needs_review


def test_secondary_sources_never_decide() -> None:
    """OpenAlex and Crossref values alone cannot open the gate."""
    decision = resolve_licence([ev(F.OPENALEX_LICENSE, "cc-by")], today=TODAY)
    assert not decision.permissions.can_display


def test_no_evidence_at_all_is_rejected_without_review() -> None:
    """No licence means no permission (fail closed) and nothing for a human to judge."""
    decision = resolve_licence([], today=TODAY)
    assert not decision.permissions.can_display
    assert not decision.needs_review


def test_unrecognised_code_goes_to_review() -> None:
    """An unknown code fails closed but deserves a human look."""
    decision = resolve_licence([ev(F.PMC_LICENSE_CODE, "CUSTOM-PUBLISHER")], today=TODAY)
    assert decision.needs_review
    assert not decision.permissions.can_display


def test_nc_nd_is_display_only_and_non_commercial() -> None:
    """CC BY-NC-ND (the largest NC group in PMC) may be shown, never rewritten."""
    decision = resolve_licence([ev(F.PMC_LICENSE_CODE, "CC BY-NC-ND")], today=TODAY)
    assert decision.permissions.can_display
    assert not decision.permissions.can_rewrite
    assert decision.permissions.non_commercial
    assert decision.permissions.output_licence is None


def test_share_alike_sets_the_output_licence() -> None:
    """A CC BY-SA paper's rewrite must be released under CC BY-SA."""
    decision = resolve_licence([ev(F.PMC_LICENSE_CODE, "CC BY-SA")], today=TODAY)
    assert decision.permissions.output_licence is not None
    assert decision.permissions.output_licence.family is LicenceFamily.CC_BY_SA
    assert decision.permissions.share_alike


def test_proposed_licence_is_the_top_recognised_value() -> None:
    """The reviewer is offered the highest-precedence recognised licence."""
    proposal = proposed_licence(
        [ev(F.JATS_ALI_LICENSE_REF, CC_BY_4), ev(F.PMC_LICENSE_CODE, "CC BY-NC")]
    )
    assert proposal.family is LicenceFamily.CC_BY_NC
    assert proposed_licence([ev(F.JATS_LICENSE_P, "prose")]).family is LicenceFamily.UNKNOWN
