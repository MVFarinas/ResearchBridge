"""Tests for the §1.1 licence gate in rbcore.licences.permissions."""

from __future__ import annotations

import pytest

from rbcore.licences import (
    NO_PERMISSIONS,
    Licence,
    LicenceEvidence,
    LicenceFamily,
    LicenceField,
    LicenceStatement,
    PermissionsBlock,
    decide,
    decide_figure,
    derive_permissions,
)

F = LicenceFamily
ALI = LicenceField.JATS_ALI_LICENSE_REF
HREF = LicenceField.JATS_LICENSE_XLINK_HREF
PROSE = LicenceField.JATS_LICENSE_P
LTYPE = LicenceField.JATS_LICENSE_TYPE


# decisions.md §1.1 table plus the 2026-10-13 addendum, one row per family. Each row
# holds the family, then the display, rewrite, non-commercial, share-alike and
# attribution flags.
SECTION_1_1 = [
    (F.CC_BY, True, True, False, False, True),
    (F.CC_BY_SA, True, True, False, True, True),
    (F.CC_BY_ND, True, False, False, False, True),
    (F.CC_BY_NC, True, True, True, False, True),
    (F.CC_BY_NC_SA, True, True, True, True, True),
    (F.CC_BY_NC_ND, True, False, True, False, True),  # the addendum's missing row
    (F.CC0, True, True, False, False, False),
    (F.PUBLIC_DOMAIN, True, True, False, False, False),
    (F.ALL_RIGHTS_RESERVED, False, False, False, False, False),
    (F.TDM, False, False, False, False, False),
    (F.ARXIV_NONEXCLUSIVE, False, False, False, False, False),
    (F.UNKNOWN, False, False, False, False, False),
]


@pytest.mark.parametrize(
    ("family", "display", "rewrite", "non_commercial", "share_alike", "attribution"),
    SECTION_1_1,
)
def test_section_1_1_table(
    family: LicenceFamily,
    display: bool,
    rewrite: bool,
    non_commercial: bool,
    share_alike: bool,
    attribution: bool,
) -> None:
    """Every row of the §1.1 table maps to the documented permissions."""
    permissions = derive_permissions(Licence(family, "4.0"))
    assert permissions.can_display is display
    assert permissions.can_rewrite is rewrite
    assert permissions.non_commercial is non_commercial
    assert permissions.share_alike is share_alike
    assert permissions.attribution_required is attribution


def test_every_family_is_covered_by_the_table() -> None:
    """The table test covers every licence family, so none is gated by accident."""
    assert {row[0] for row in SECTION_1_1} == set(LicenceFamily)


def test_share_alike_rewrite_is_released_under_the_same_licence() -> None:
    """A rewrite of a CC BY-SA paper must itself be CC BY-SA (same version)."""
    licence = Licence(F.CC_BY_SA, "4.0")
    assert derive_permissions(licence).output_licence == licence
    nc_sa = Licence(F.CC_BY_NC_SA, "3.0", "igo")
    assert derive_permissions(nc_sa).output_licence == nc_sa


def test_output_licence_mirrors_source_and_is_absent_without_rewrite() -> None:
    """Rewrites mirror the source licence; no-derivatives licences have no output licence."""
    assert derive_permissions(Licence(F.CC_BY, "4.0")).output_licence == Licence(F.CC_BY, "4.0")
    assert derive_permissions(Licence(F.CC0, "1.0")).output_licence == Licence(F.CC0, "1.0")
    assert derive_permissions(Licence(F.CC_BY_ND, "4.0")).output_licence is None
    assert derive_permissions(Licence(F.CC_BY_NC_ND, "4.0")).output_licence is None


@pytest.mark.parametrize("family", [F.ALL_RIGHTS_RESERVED, F.TDM, F.ARXIV_NONEXCLUSIVE, F.UNKNOWN])
def test_closed_licences_get_no_permissions(family: LicenceFamily) -> None:
    """Closed or unknown licences fail closed: nothing is displayed or rewritten."""
    assert derive_permissions(Licence(family)) == NO_PERMISSIONS


# ----- decide(): from evidence to one decision ------------------------------


def test_decide_uses_machine_readable_evidence() -> None:
    """A single ali:license_ref decides the licence and is recorded as the source."""
    evidence = [
        LicenceEvidence(ALI, "https://creativecommons.org/licenses/by/4.0/"),
        LicenceEvidence(PROSE, "This article is distributed under CC BY."),
    ]
    decision = decide(evidence)
    assert decision.licence == Licence(F.CC_BY, "4.0")
    assert decision.source_field is ALI
    assert decision.permissions.can_rewrite
    assert not decision.needs_review


def test_decide_prose_only_fails_closed_and_needs_review() -> None:
    """license-p prose is never used for automated decisions."""
    decision = decide(
        [LicenceEvidence(PROSE, "Distributed under https://creativecommons.org/licenses/by/4.0/")]
    )
    assert decision.licence.family is F.UNKNOWN
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert decision.source is None
    assert "jats:license-p" in " ".join(decision.reasons)


def test_decide_license_type_alone_is_not_authoritative() -> None:
    """@license-type is an uncontrolled vocabulary, so it never approves anything."""
    decision = decide([LicenceEvidence(LTYPE, "cc-by")])
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review


def test_decide_no_evidence_fails_closed_without_review() -> None:
    """With no licence at all there is nothing to review: the paper is simply excluded."""
    decision = decide([])
    assert decision.permissions == NO_PERMISSIONS
    assert not decision.needs_review


def test_decide_secondary_aggregator_fields_never_gate() -> None:
    """Crossref/OpenAlex licences are secondary signals, never the gate."""
    decision = decide(
        [
            LicenceEvidence(
                LicenceField.OPENALEX_LICENSE, "https://creativecommons.org/licenses/by/4.0/"
            )
        ]
    )
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review


def test_decide_conflicting_families_fail_closed() -> None:
    """Machine-readable values that disagree on family go to review."""
    decision = decide(
        [
            LicenceEvidence(ALI, "https://creativecommons.org/licenses/by/4.0/"),
            LicenceEvidence(HREF, "https://creativecommons.org/licenses/by-nd/4.0/"),
        ]
    )
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert "conflicting" in decision.reasons[0]


def test_decide_known_plus_unrecognised_value_conflicts() -> None:
    """A recognised CC URI alongside an unrecognised publisher licence is a conflict."""
    decision = decide(
        [
            LicenceEvidence(ALI, "https://creativecommons.org/licenses/by/4.0/"),
            LicenceEvidence(HREF, "https://www.elsevier.com/tdm/userlicense/1.0/"),
        ]
    )
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review


def test_decide_same_family_different_versions_agree() -> None:
    """Versions do not change the gate, so by/3.0 and by/4.0 agree; the first wins."""
    decision = decide(
        [
            LicenceEvidence(ALI, "http://creativecommons.org/licenses/by/4.0/"),
            LicenceEvidence(HREF, "http://creativecommons.org/licenses/by/3.0/"),
        ]
    )
    assert decision.licence == Licence(F.CC_BY, "4.0")
    assert decision.source_field is ALI
    assert decision.permissions.can_rewrite


def test_decide_unrecognised_single_value_needs_review() -> None:
    """An unrecognised machine-readable value fails closed and is flagged for review."""
    decision = decide([LicenceEvidence(HREF, "http://www.springer.com/tdm")])
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert decision.source_field is HREF


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (LicenceField.PMC_LICENSE_CODE, "TDM"),
        (LicenceField.ARXIV_OAI_LICENSE, "http://arxiv.org/licenses/nonexclusive-distrib/1.0/"),
        (LicenceField.BIORXIV_LICENSE, "cc_no"),
    ],
)
def test_decide_definite_no_is_not_sent_to_review(field: LicenceField, value: str) -> None:
    """TDM, arXiv non-exclusive and bioRxiv no-reuse are clear refusals, not review cases."""
    decision = decide([LicenceEvidence(field, value)])
    assert decision.permissions == NO_PERMISSIONS
    assert not decision.needs_review
    assert decision.source_field is field


@pytest.mark.parametrize(
    ("field", "value", "display", "rewrite", "non_commercial"),
    [
        (LicenceField.PMC_LICENSE_CODE, "CC BY-NC-ND", True, False, True),
        (LicenceField.EUROPE_PMC_LICENSE, "cc by-sa", True, True, False),
        (LicenceField.BIORXIV_LICENSE, "cc_by_nc", True, True, True),
        (
            LicenceField.ARXIV_OAI_LICENSE,
            "http://creativecommons.org/licenses/by-nd/4.0/",
            True,
            False,
            False,
        ),
        (LicenceField.PMC_LICENSE_CODE, "CC0", True, True, False),
    ],
)
def test_decide_per_source_codes(
    field: LicenceField, value: str, display: bool, rewrite: bool, non_commercial: bool
) -> None:
    """Licence codes from each authoritative source go through the same gate."""
    permissions = decide([LicenceEvidence(field, value)]).permissions
    assert (permissions.can_display, permissions.can_rewrite, permissions.non_commercial) == (
        display,
        rewrite,
        non_commercial,
    )


# ----- decide_figure(): figure-level overrides -------------------------------


def _article_cc_by() -> PermissionsBlock:
    """Synthetic article permissions block with a CC BY 4.0 ali:license_ref."""
    return PermissionsBlock(
        licences=(
            LicenceStatement(ali_license_refs=("https://creativecommons.org/licenses/by/4.0/",)),
        )
    )


def test_figure_without_permissions_inherits_article_decision() -> None:
    """Objects without their own block take the article licence (JATS4R)."""
    article = decide(_article_cc_by().evidence())
    figure = decide_figure(article, None)
    assert figure.inherited
    assert figure.licence == article.licence
    assert figure.permissions == article.permissions


def test_figure_with_more_restrictive_licence_overrides_article() -> None:
    """A CC BY-NC figure in a CC BY article is display/rewrite but non-commercial."""
    article = decide(_article_cc_by().evidence())
    block = PermissionsBlock(
        copyright_holders=("Pandey et al",),
        licences=(
            LicenceStatement(ali_license_refs=("https://creativecommons.org/licenses/by-nc/4.0/",)),
        ),
    )
    figure = decide_figure(article, block)
    assert not figure.inherited
    assert figure.licence == Licence(F.CC_BY_NC, "4.0")
    assert figure.permissions.non_commercial


def test_figure_with_no_derivatives_licence_cannot_be_rewritten() -> None:
    """A CC BY-ND figure can be shown but its caption may not be rewritten."""
    article = decide(_article_cc_by().evidence())
    block = PermissionsBlock(
        licences=(LicenceStatement(xlink_href="https://creativecommons.org/licenses/by-nd/4.0/"),)
    )
    figure = decide_figure(article, block)
    assert figure.permissions.can_display
    assert not figure.permissions.can_rewrite


def test_figure_with_copyright_only_block_fails_closed() -> None:
    """A block with only copyright and prose ("not covered by CC-BY") fails closed."""
    article = decide(_article_cc_by().evidence())
    block = PermissionsBlock(
        copyright_statement="© 2002 Springer Nature. All rights reserved",
        copyright_holders=("Springer Nature",),
        licences=(LicenceStatement(prose="It is not covered by the CC-BY 4.0 licence."),),
    )
    figure = decide_figure(article, block)
    assert figure.permissions == NO_PERMISSIONS
    assert figure.needs_review
    assert "Springer Nature" in figure.reasons[0]


def test_figure_licence_can_be_more_permissive_than_article() -> None:
    """The figure's own licence governs the figure even inside a CC BY-ND article."""
    article = decide([LicenceEvidence(ALI, "https://creativecommons.org/licenses/by-nd/4.0/")])
    block = PermissionsBlock(
        licences=(LicenceStatement(xlink_href="http://creativecommons.org/publicdomain/zero/1.0/"),)
    )
    figure = decide_figure(article, block)
    assert figure.permissions.can_rewrite
    assert not article.permissions.can_rewrite


def test_statement_evidence_order_is_machine_readable_first() -> None:
    """LicenceStatement.evidence lists ali refs, then href, then type, then prose."""
    statement = LicenceStatement(
        xlink_href="http://creativecommons.org/licenses/by/4.0/",
        ali_license_refs=("https://creativecommons.org/licenses/by/4.0/",),
        ali_specific_uses=("textmining",),
        license_type="open-access",
        prose="Some prose.",
    )
    assert [e.field for e in statement.evidence()] == [ALI, HREF, LTYPE, PROSE]
    assert statement.evidence()[0].specific_use == "textmining"
