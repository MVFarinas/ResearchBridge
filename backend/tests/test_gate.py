"""The persisted gate: decisions, part overrides and the review queue (synthetic data)."""

from __future__ import annotations

from datetime import date

import pytest
from support import synthetic_block, synthetic_code, synthetic_content, synthetic_version

from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import (
    BlockScope,
    ContentState,
    Figure,
    GateStatus,
    LicenceReview,
    Paragraph,
    ReviewScope,
    ReviewStatus,
)
from rb_backend.corpus.reviews import ReviewError, resolve_review
from rbcore.licences import AliLicenceRef, LicenceField, LicenceStatement, PermissionsBlock

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 13)
CC_BY_4 = "http://creativecommons.org/licenses/by/4.0/"


def ali_block(uri: str, *, context: str = "article-meta", **dates: str) -> PermissionsBlock:
    """A synthetic permissions block with one ali:license_ref."""
    return PermissionsBlock(
        licences=(LicenceStatement(ali_license_refs=(AliLicenceRef(uri, None, **dates),)),),
        context=context,
    )


def prose_block(text: str, *, context: str, inner: bool = False) -> PermissionsBlock:
    """A synthetic permissions block with only license-p prose and a copyright holder."""
    return PermissionsBlock(
        copyright_holders=("Synthetic Rights Holder",),
        licences=(LicenceStatement(prose=text),),
        context=context,
        inner=inner,
    )


def test_agreeing_code_approves_version_and_parts_inherit() -> None:
    """A CC BY code with parsed content approves the version; parts inherit it."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")

    assert evaluate_version(version, today=TODAY) == GateStatus.APPROVED
    assert (version.can_display, version.can_rewrite) == (True, True)
    assert version.output_licence_family == "cc-by"
    assert version.decision_source == LicenceField.PMC_LICENSE_CODE.value
    for part in [
        *Paragraph.objects.filter(version=version),
        *Figure.objects.filter(version=version),
    ]:
        assert part.gate_status == GateStatus.APPROVED
        assert part.can_rewrite
        assert part.decision_source == "inherited:pmc:license_code"
    assert not LicenceReview.objects.exists()


def test_licence_without_parsed_content_is_pending() -> None:
    """A displayable licence waits for the full text before anything is approved."""
    version = synthetic_version(content_state=ContentState.NONE)
    synthetic_code(version, "CC BY")
    assert evaluate_version(version, today=TODAY) == GateStatus.PENDING
    assert not version.can_display
    assert version.licence_family == "cc-by"
    assert "full text not parsed yet" in version.decision_reasons


def test_tdm_is_rejected_without_review_and_parts_wait() -> None:
    """TDM author manuscripts are refused outright; nothing is queued."""
    version = synthetic_version(content_state=ContentState.SKIPPED)
    synthetic_code(version, "TDM")
    assert evaluate_version(version, today=TODAY) == GateStatus.REJECTED
    assert version.licence_family == "tdm"
    assert not LicenceReview.objects.exists()


def test_conflict_opens_exactly_one_review_and_stays_idempotent() -> None:
    """Conflicting sources fail closed with one open review, however often re-run."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    synthetic_code(version, "cc by-nd", LicenceField.EUROPE_PMC_LICENSE)

    for _ in range(3):
        assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW
    review = LicenceReview.objects.get()
    assert review.status == ReviewStatus.OPEN
    assert review.scope == ReviewScope.VERSION
    assert review.proposed_family == "cc-by"
    assert {item["field"] for item in review.evidence} == {
        "pmc:license_code",
        "europepmc:license",
    }
    assert not version.can_display
    assert f"awaiting licence review #{review.pk}" in version.decision_reasons
    assert set(Paragraph.objects.values_list("gate_status", flat=True)) == {GateStatus.PENDING}


def test_resolution_approves_and_survives_re_evaluation() -> None:
    """A reviewer's approval applies, and keeps applying while the evidence is unchanged."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    synthetic_code(version, "cc by-nd", LicenceField.EUROPE_PMC_LICENSE)
    evaluate_version(version, today=TODAY)
    review = LicenceReview.objects.get()

    status = resolve_review(
        review, approve=True, licence_value="CC BY-ND", note="Publisher confirms ND.", reviewer=None
    )
    assert status == GateStatus.APPROVED
    version.refresh_from_db()
    assert (version.can_display, version.can_rewrite) == (True, False)
    assert version.decision_source == f"licence-review:{review.pk}"
    assert evaluate_version(version, today=TODAY) == GateStatus.APPROVED
    assert set(Paragraph.objects.values_list("can_rewrite", flat=True)) == {False}


def test_changed_evidence_reopens_review_instead_of_reusing_the_answer() -> None:
    """A resolution is tied to its evidence: new evidence means a new review."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    synthetic_code(version, "cc by-nd", LicenceField.EUROPE_PMC_LICENSE)
    evaluate_version(version, today=TODAY)
    first = LicenceReview.objects.get()
    resolve_review(first, approve=True, licence_value="CC BY", note="Checked.", reviewer=None)

    synthetic_code(version, "cc by-nc", LicenceField.EUROPE_PMC_LICENSE)
    assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW
    assert LicenceReview.objects.filter(status=ReviewStatus.OPEN).count() == 1
    first.refresh_from_db()
    assert first.status == ReviewStatus.APPROVED


def test_rejection_and_refusing_resolution_both_reject() -> None:
    """Rejecting, or approving with a licence that refuses display, rejects the version."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version, today=TODAY)
    review = LicenceReview.objects.get()
    assert (
        resolve_review(review, approve=False, licence_value="", note="No licence.", reviewer=None)
        == GateStatus.REJECTED
    )

    other = synthetic_version(pmcid="PMC900000002")
    synthetic_content(other)
    synthetic_code(other, "SOMETHING-UNKNOWN")
    evaluate_version(other, today=TODAY)
    review = LicenceReview.objects.get(version=other)
    assert (
        resolve_review(review, approve=True, licence_value="TDM", note="Manuscript.", reviewer=None)
        == GateStatus.REJECTED
    )


@pytest.mark.parametrize(
    ("approve", "licence", "note", "message"),
    [
        (True, "not a licence", "x", "not a recognised licence"),
        (True, "CC BY", "  ", "justification"),
    ],
)
def test_resolve_review_validates_input(
    approve: bool, licence: str, note: str, message: str
) -> None:
    """Approvals need a recognised licence and every resolution needs a note."""
    version = synthetic_version()
    synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version, today=TODAY)
    review = LicenceReview.objects.get()
    with pytest.raises(ReviewError, match=message):
        resolve_review(review, approve=approve, licence_value=licence, note=note, reviewer=None)
    review.refresh_from_db()
    assert review.status == ReviewStatus.OPEN


def test_only_open_reviews_can_be_resolved() -> None:
    """A resolved review cannot be resolved again."""
    version = synthetic_version()
    synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version, today=TODAY)
    review = LicenceReview.objects.get()
    resolve_review(review, approve=False, licence_value="", note="No.", reviewer=None)
    with pytest.raises(ReviewError, match="not open"):
        resolve_review(review, approve=True, licence_value="CC BY", note="Yes.", reviewer=None)


def test_unattached_block_sends_version_to_review() -> None:
    """A permissions block the parser could not attach blocks automatic approval."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    synthetic_block(
        version,
        prose_block("Supplementary video (c) Synthetic Studio.", context="supplementary-material"),
        scope=BlockScope.UNATTACHED,
    )
    assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW
    assert "supplementary-material" in LicenceReview.objects.get().reasons[-1]


def test_failed_parse_sends_version_to_review() -> None:
    """Unparsed full text could hide part-level restrictions, so it needs a human."""
    version = synthetic_version(content_state=ContentState.FAILED)
    version.content_error = "JATS parse error: synthetic"
    version.save()
    synthetic_code(version, "CC BY")
    assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW


def test_figure_prose_override_fails_closed_with_its_own_review() -> None:
    """A figure with only prose in its own permissions is hidden and queued; the paper is not."""
    version = synthetic_version()
    synthetic_content(version, figures=2)
    synthetic_code(version, "CC BY")
    figure = Figure.objects.get(version=version, stable_id="fig1")
    synthetic_block(
        version,
        prose_block("Not covered by the CC BY licence (synthetic).", context="fig"),
        scope=BlockScope.FIGURE,
        figure=figure,
    )

    assert evaluate_version(version, today=TODAY) == GateStatus.APPROVED
    figure.refresh_from_db()
    assert figure.gate_status == GateStatus.REVIEW
    assert not figure.can_display
    review = LicenceReview.objects.get()
    assert (review.scope, review.figure_id) == (ReviewScope.FIGURE, figure.pk)
    assert Figure.objects.get(version=version, stable_id="fig2").can_display


def test_figure_licence_override_narrows_permissions() -> None:
    """A figure under CC BY-ND inside a CC BY paper may be shown, not rewritten."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    figure = Figure.objects.get(version=version)
    synthetic_block(
        version,
        ali_block("https://creativecommons.org/licenses/by-nd/4.0/", context="fig"),
        scope=BlockScope.FIGURE,
        figure=figure,
    )
    evaluate_version(version, today=TODAY)
    figure.refresh_from_db()
    assert (figure.gate_status, figure.can_display, figure.can_rewrite) == (
        GateStatus.APPROVED,
        True,
        False,
    )
    assert figure.licence_family == "cc-by-nd"


def test_figure_review_resolution_applies_to_that_figure() -> None:
    """Resolving a figure review opens just that figure."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    figure = Figure.objects.get(version=version)
    synthetic_block(
        version,
        prose_block("Reproduced with permission (synthetic).", context="fig"),
        scope=BlockScope.FIGURE,
        figure=figure,
    )
    evaluate_version(version, today=TODAY)
    review = LicenceReview.objects.get(scope=ReviewScope.FIGURE)
    resolve_review(
        review, approve=True, licence_value="CC BY-NC 4.0", note="Checked.", reviewer=None
    )
    figure.refresh_from_db()
    assert (figure.can_display, figure.non_commercial) == (True, True)


def test_inner_block_allowing_less_closes_the_paragraph() -> None:
    """A nested object licensed more narrowly closes its paragraph for review."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    paragraph = Paragraph.objects.get(version=version, stable_id="body-p1")
    synthetic_block(
        version,
        ali_block("https://creativecommons.org/licenses/by-nc-nd/4.0/", context="disp-quote"),
        scope=BlockScope.PARAGRAPH,
        paragraph=paragraph,
    )
    paragraph_block = paragraph.permission_blocks.get()
    paragraph_block.inner = True
    paragraph_block.save()

    evaluate_version(version, today=TODAY)
    paragraph.refresh_from_db()
    assert paragraph.gate_status == GateStatus.REVIEW
    assert not paragraph.can_display
    assert Paragraph.objects.get(version=version, stable_id="body-p2").can_rewrite


def test_parts_wait_and_part_reviews_close_while_the_version_is_not_approved() -> None:
    """When the version leaves approval, part reviews are superseded and parts wait."""
    version = synthetic_version()
    synthetic_content(version)
    code = synthetic_code(version, "CC BY")
    figure = Figure.objects.get(version=version)
    synthetic_block(
        version,
        prose_block("Synthetic prose.", context="fig"),
        scope=BlockScope.FIGURE,
        figure=figure,
    )
    evaluate_version(version, today=TODAY)
    assert LicenceReview.objects.get().status == ReviewStatus.OPEN

    code.raw_value = "TDM"
    code.save()
    assert evaluate_version(version, today=TODAY) == GateStatus.REJECTED
    assert LicenceReview.objects.get().status == ReviewStatus.SUPERSEDED
    figure.refresh_from_db()
    assert figure.gate_status == GateStatus.PENDING


def test_embargo_start_date_is_honoured_and_rechecked_later() -> None:
    """A licence that starts in the future is not in force until that date."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_block(version, ali_block(CC_BY_4, start_date="2027-01-01"), scope=BlockScope.ARTICLE)
    assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW
    assert evaluate_version(version, today=date(2027, 2, 1)) == GateStatus.APPROVED
    assert LicenceReview.objects.get().status == ReviewStatus.SUPERSEDED


def test_expired_licence_fails_closed() -> None:
    """A licence whose end date has passed approves nothing."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_block(version, ali_block(CC_BY_4, end_date="2025-01-01"), scope=BlockScope.ARTICLE)
    assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW
    assert not version.can_display
