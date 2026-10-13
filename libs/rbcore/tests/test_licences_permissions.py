"""Tests for the §1.1 licence gate in rbcore.licences.permissions."""

from __future__ import annotations

from datetime import date

import pytest

from rbcore.licences import (
    NO_PERMISSIONS,
    AliLicenceRef,
    Licence,
    LicenceEvidence,
    LicenceFamily,
    LicenceField,
    LicenceStatement,
    PermissionsBlock,
    decide,
    decide_part,
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


# ----- decide_part(): figure, table and paragraph overrides -------------------------------


def _article_cc_by() -> PermissionsBlock:
    """Synthetic article permissions block with a CC BY 4.0 ali:license_ref."""
    return PermissionsBlock(
        licences=(
            LicenceStatement(
                ali_license_refs=(AliLicenceRef("https://creativecommons.org/licenses/by/4.0/"),)
            ),
        )
    )


def test_figure_without_permissions_inherits_article_decision() -> None:
    """Objects without their own block take the article licence (JATS4R)."""
    article = decide(_article_cc_by().evidence())
    figure = decide_part(article, ())
    assert figure.inherited
    assert figure.licence == article.licence
    assert figure.permissions == article.permissions


def test_figure_with_more_restrictive_licence_overrides_article() -> None:
    """A CC BY-NC figure in a CC BY article is display/rewrite but non-commercial."""
    article = decide(_article_cc_by().evidence())
    block = PermissionsBlock(
        copyright_holders=("Pandey et al",),
        licences=(
            LicenceStatement(
                ali_license_refs=(AliLicenceRef("https://creativecommons.org/licenses/by-nc/4.0/"),)
            ),
        ),
    )
    figure = decide_part(article, (block,))
    assert not figure.inherited
    assert figure.licence == Licence(F.CC_BY_NC, "4.0")
    assert figure.permissions.non_commercial


def test_figure_with_no_derivatives_licence_cannot_be_rewritten() -> None:
    """A CC BY-ND figure can be shown but its caption may not be rewritten."""
    article = decide(_article_cc_by().evidence())
    block = PermissionsBlock(
        licences=(LicenceStatement(xlink_href="https://creativecommons.org/licenses/by-nd/4.0/"),)
    )
    figure = decide_part(article, (block,))
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
    figure = decide_part(article, (block,))
    assert figure.permissions == NO_PERMISSIONS
    assert figure.needs_review
    assert "Springer Nature" in figure.reasons[0]


def test_figure_licence_can_be_more_permissive_than_article() -> None:
    """The figure's own licence governs the figure even inside a CC BY-ND article."""
    article = decide([LicenceEvidence(ALI, "https://creativecommons.org/licenses/by-nd/4.0/")])
    block = PermissionsBlock(
        licences=(LicenceStatement(xlink_href="http://creativecommons.org/publicdomain/zero/1.0/"),)
    )
    figure = decide_part(article, (block,))
    assert figure.permissions.can_rewrite
    assert not article.permissions.can_rewrite


def test_statement_evidence_order_is_machine_readable_first() -> None:
    """LicenceStatement.evidence lists ali refs, then href, then type, then prose."""
    statement = LicenceStatement(
        xlink_href="http://creativecommons.org/licenses/by/4.0/",
        ali_license_refs=(
            AliLicenceRef(
                "https://creativecommons.org/licenses/by/4.0/", specific_use="textmining"
            ),
        ),
        license_type="open-access",
        prose="Some prose.",
    )
    assert [e.field for e in statement.evidence()] == [ALI, HREF, LTYPE, PROSE]
    assert statement.evidence()[0].specific_use == "textmining"


# ----- NISO ALI dates ---------------------------------------------------------

TODAY = date(2026, 10, 13)
CC_BY_URI = "https://creativecommons.org/licenses/by/4.0/"


def test_future_start_date_fails_closed_with_review() -> None:
    """An embargoed licence (start_date in the future) is not in force yet."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, start_date="2027-01-01")], today=TODAY)
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert "applies only from 2027-01-01" in decision.reasons[0]


def test_past_start_date_is_in_force() -> None:
    """A licence whose start_date has passed applies normally."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, start_date="2020-01-01")], today=TODAY)
    assert decision.permissions.can_rewrite
    assert not decision.needs_review


def test_start_date_today_is_in_force() -> None:
    """The start date itself is the first day the licence applies."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, start_date="2026-10-13")], today=TODAY)
    assert decision.permissions.can_rewrite


def test_default_today_still_honours_far_future_embargo() -> None:
    """Without an injected date the real date is used; 2099 is still in the future."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, start_date="2099-01-01")])
    assert decision.permissions == NO_PERMISSIONS


@pytest.mark.parametrize("raw", ["soon", "2026-13-01", "01/02/2026"])
def test_unparsable_dates_fail_closed(raw: str) -> None:
    """A date the gate cannot read is treated as not in force."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, start_date=raw)], today=TODAY)
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert repr(raw) in decision.reasons[0]


def test_date_time_values_use_their_date_part() -> None:
    """ISO date-times such as 2020-01-01T00:00:00Z are accepted."""
    decision = decide(
        [LicenceEvidence(ALI, CC_BY_URI, start_date="2020-01-01T00:00:00Z")], today=TODAY
    )
    assert decision.permissions.can_rewrite


def test_embargo_transition_between_two_dated_references() -> None:
    """Publisher licence until the embargo ends, then CC BY-NC-ND: the later start wins."""
    evidence = [
        LicenceEvidence(
            ALI, "https://www.elsevier.com/tdm/userlicense/1.0/", start_date="2025-01-01"
        ),
        LicenceEvidence(
            ALI, "https://creativecommons.org/licenses/by-nc-nd/4.0/", start_date="2026-06-01"
        ),
    ]
    before = decide(evidence, today=date(2026, 1, 1))
    assert before.permissions == NO_PERMISSIONS
    assert before.needs_review

    after = decide(evidence, today=date(2026, 7, 1))
    assert after.licence == Licence(F.CC_BY_NC_ND, "4.0")
    assert after.permissions.can_display
    assert not after.permissions.can_rewrite
    assert not after.needs_review
    assert any("superseded" in reason for reason in after.reasons)


def test_end_date_in_the_past_fails_closed() -> None:
    """A licence that has ended no longer grants anything."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, end_date="2025-12-31")], today=TODAY)
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert "ended on 2025-12-31" in decision.reasons[0]


def test_end_date_in_the_future_grants_but_needs_review() -> None:
    """A licence that will end still applies today, but a human should know."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, end_date="2030-01-01")], today=TODAY)
    assert decision.permissions.can_rewrite
    assert decision.needs_review
    assert "ends on 2030-01-01" in decision.reasons[-1]


# ----- @specific-use and @license-type signals --------------------------------


def test_scoped_only_evidence_keeps_licence_but_needs_review() -> None:
    """A sole text-mining-scoped CC reference grants as before but is flagged."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, specific_use="textmining")])
    assert decision.permissions.can_rewrite
    assert decision.needs_review
    assert "@specific-use (textmining)" in decision.reasons[-1]


def test_scoped_evidence_confirmed_by_an_unscoped_value_needs_no_review() -> None:
    """An agreeing unscoped value (xlink:href or a PMC license_code) clears the flag."""
    scoped = LicenceEvidence(ALI, CC_BY_URI, specific_use="textmining")
    for confirming in (
        LicenceEvidence(HREF, "http://creativecommons.org/licenses/by/4.0/"),
        LicenceEvidence(LicenceField.PMC_LICENSE_CODE, "CC BY"),
    ):
        decision = decide([scoped, confirming])
        assert decision.permissions.can_rewrite
        assert not decision.needs_review


def test_version_of_record_scope_is_not_a_narrowing_scope() -> None:
    """specific-use="vor" names the article itself, so it needs no review."""
    decision = decide([LicenceEvidence(ALI, CC_BY_URI, specific_use="VoR")])
    assert not decision.needs_review


def test_contradicting_license_type_needs_review() -> None:
    """A closed @license-type next to an open href is a signal a human should see."""
    decision = decide(
        [LicenceEvidence(HREF, CC_BY_URI), LicenceEvidence(LTYPE, "all-rights-reserved")]
    )
    assert decision.permissions.can_display
    assert decision.needs_review
    assert "all-rights-reserved" in decision.reasons[-1]


def test_uninformative_license_type_needs_no_review() -> None:
    """Common uncontrolled values such as "open-access" say nothing about the licence."""
    decision = decide([LicenceEvidence(HREF, CC_BY_URI), LicenceEvidence(LTYPE, "open-access")])
    assert not decision.needs_review


# ----- decide_part(): several blocks ------------------------------------------


def test_part_with_several_blocks_fails_closed_even_if_all_are_open() -> None:
    """With two blocks the gate never chooses; a human resolves which applies where."""
    article = decide(_article_cc_by().evidence())
    open_block = PermissionsBlock(
        licences=(LicenceStatement(xlink_href=CC_BY_URI),), context="fig-group"
    )
    decision = decide_part(article, (open_block, open_block))
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert "(fig-group, fig-group)" in decision.reasons[0]


def test_part_block_with_embargoed_licence_is_reported_as_a_date_problem() -> None:
    """A part's own embargoed licence fails closed with the date reason, not a prose reason."""
    article = decide(_article_cc_by().evidence())
    block = PermissionsBlock(
        licences=(
            LicenceStatement(ali_license_refs=(AliLicenceRef(CC_BY_URI, start_date="2099-01-01"),)),
        ),
        context="fig",
    )
    decision = decide_part(article, (block,), today=TODAY)
    assert decision.permissions == NO_PERMISSIONS
    assert "start_date in the future" in decision.reasons[0]


def test_future_reference_is_set_aside_while_an_earlier_dated_one_is_in_force() -> None:
    """Before an embargo transition the earlier dated licence applies (review probe P8)."""
    evidence = [
        LicenceEvidence(
            ALI, "https://creativecommons.org/licenses/by-nc-nd/4.0/", start_date="2024-01-01"
        ),
        LicenceEvidence(ALI, CC_BY_URI, start_date="2027-01-01"),
    ]
    before = decide(evidence, today=TODAY)
    assert before.licence == Licence(F.CC_BY_NC_ND, "4.0")
    assert before.permissions.can_display
    assert not before.permissions.can_rewrite
    assert not before.needs_review
    assert any("applies only from 2027-01-01" in reason for reason in before.reasons)

    after = decide(evidence, today=date(2027, 1, 1))
    assert after.licence == Licence(F.CC_BY, "4.0")
    assert after.permissions.can_rewrite


def test_future_reference_beside_only_undated_values_still_fails_closed() -> None:
    """An undated href beside a future-dated ref may mean the same embargo: never open early."""
    decision = decide(
        [
            LicenceEvidence(ALI, CC_BY_URI, start_date="2099-01-01"),
            LicenceEvidence(HREF, CC_BY_URI),
        ],
        today=TODAY,
    )
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert "start_date in the future" in decision.reasons[0]


# ----- decide_part(): blocks on objects nested inside a part ------------------

ND_URI = "https://creativecommons.org/licenses/by-nd/4.0/"


def _inner(uri: str | None, context: str = "media") -> PermissionsBlock:
    """Synthetic inner permissions block with an xlink:href licence (or copyright only)."""
    if uri is None:
        return PermissionsBlock(
            copyright_holders=("Synthetic Holder",),
            licences=(LicenceStatement(prose="All rights reserved."),),
            context=context,
            inner=True,
        )
    return PermissionsBlock(
        licences=(LicenceStatement(xlink_href=uri),), context=context, inner=True
    )


def test_inner_block_never_widens_a_no_derivatives_part() -> None:
    """A CC BY media item inside a paragraph of a CC BY-ND article keeps the paragraph ND."""
    article = decide([LicenceEvidence(ALI, ND_URI)])
    decision = decide_part(article, (_inner(CC_BY_URI),))
    assert decision.licence == Licence(F.CC_BY_ND, "4.0")
    assert decision.permissions.can_display
    assert not decision.permissions.can_rewrite
    assert decision.inherited
    assert "media inside the part has its own licence (CC BY 4.0)" in decision.reasons[-1]


@pytest.mark.parametrize(
    ("article_uri", "inner_uri"),
    [
        (CC_BY_URI, "https://creativecommons.org/licenses/by-nc/4.0/"),
        (CC_BY_URI, ND_URI),
        (CC_BY_URI, "https://creativecommons.org/licenses/by-sa/4.0/"),
        ("https://creativecommons.org/publicdomain/zero/1.0/", CC_BY_URI),
        (CC_BY_URI, None),
    ],
)
def test_inner_block_that_allows_less_closes_the_part(
    article_uri: str, inner_uri: str | None
) -> None:
    """Non-commercial, no-derivatives, share-alike, attribution or closed inner objects close it."""
    article = decide([LicenceEvidence(ALI, article_uri)])
    decision = decide_part(article, (_inner(inner_uri),))
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    assert "allow less than the part's own licence" in decision.reasons[0]


def test_inner_block_under_the_same_licence_changes_nothing() -> None:
    """A CC BY inline object in a CC BY paragraph leaves the decision and review flag as is."""
    article = decide(_article_cc_by().evidence())
    decision = decide_part(article, (_inner("http://creativecommons.org/licenses/by/3.0/"),))
    assert decision.permissions == article.permissions
    assert not decision.needs_review


def test_inner_block_in_a_closed_part_keeps_it_closed() -> None:
    """Nothing granted means an open inner object cannot open the part."""
    article = decide([LicenceEvidence(ALI, "https://www.example.org/all-rights-reserved")])
    decision = decide_part(article, (_inner(CC_BY_URI),))
    assert decision.permissions == NO_PERMISSIONS


def test_inner_blocks_combine_with_a_covering_block() -> None:
    """A covering block decides the part; an inner block may still narrow it."""
    article = decide(_article_cc_by().evidence())
    covering = PermissionsBlock(licences=(LicenceStatement(xlink_href=ND_URI),), context="p")
    kept = decide_part(article, (covering, _inner(CC_BY_URI)))
    assert kept.licence == Licence(F.CC_BY_ND, "4.0")
    assert not kept.inherited
    closed = decide_part(article, (covering, _inner(None)))
    assert closed.permissions == NO_PERMISSIONS
