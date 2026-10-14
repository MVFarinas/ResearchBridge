"""End-to-end ingestion against recorded bucket responses (plus named synthetic variants)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from support import RECORDED_XML, RecordedBucket, recorded_metadata

from rb_backend.annotations.models import Annotation, Provenance
from rb_backend.corpus import access
from rb_backend.corpus.models import (
    ContentState,
    Figure,
    GateStatus,
    LicenceRecord,
    LicenceReview,
    Paper,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
    ReviewScope,
)
from rb_backend.corpus.reviews import resolve_review
from rb_backend.ingestion import pipeline
from rb_backend.ingestion.pipeline import (
    PARSER_VERSION,
    IngestOutcome,
    ingest_pmc_article,
    normalise_doi,
)
from rb_backend.ingestion.pmc import PmcBucket
from rbcore.http import FetchError, PoliteFetcher
from rbcore.jats import parse_jats

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
TODAY = date(2026, 10, 13)
SYNTHETIC_PMCID = "PMC900000001"


def ingest(pmcid: str, bucket: PmcBucket, now: datetime = NOW) -> Any:
    """Ingest with fixed clocks."""
    return ingest_pmc_article(pmcid, bucket=bucket, now=now, today=TODAY)


def synthetic_jats(
    paragraphs: list[str], licence: str = "http://creativecommons.org/licenses/by/4.0/"
) -> bytes:
    """A minimal synthetic JATS article (not a real paper)."""
    body = "".join(f"<p>{text}</p>" for text in paragraphs)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<article xmlns:ali="http://www.niso.org/schemas/ali/1.0/" article-type="research-article">'
        "<front><article-meta>"
        f'<article-id pub-id-type="pmcid">{SYNTHETIC_PMCID}</article-id>'
        "<title-group><article-title>Synthetic test article</article-title></title-group>"
        f"<permissions><license><ali:license_ref>{licence}</ali:license_ref></license></permissions>"
        f"</article-meta></front><body>{body}</body></article>"
    ).encode()


def serve_synthetic(
    recorded: RecordedBucket,
    *,
    version: int,
    xml: bytes,
    code: str | None = "CC BY",
    listed: list[int] | None = None,
    **extra: Any,
) -> None:
    """Serve a synthetic article version: listing, metadata and XML with a matching MD5."""
    # Serve the XML first: its MD5 goes into the metadata's xml_url.
    version_id = f"{SYNTHETIC_PMCID}.{version}"
    digest = recorded.add_xml(version_id, xml)
    recorded.add_listing(SYNTHETIC_PMCID, listed or [version])

    # Synthetic metadata in the shape of the PMC JSON.
    recorded.add_metadata(
        {
            "pmcid": SYNTHETIC_PMCID,
            "version": version,
            "pmid": 900000001,
            "doi": "10.9999/SYNTHETIC.1",
            "title": "Synthetic test article",
            "citation": "Synthetic. 2026.",
            "is_pmc_openaccess": True,
            "is_manuscript": False,
            "is_historical_ocr": False,
            "is_retracted": False,
            "license_code": code,
            "xml_url": f"s3://pmc-oa-opendata/{version_id}/{version_id}.xml?md5={digest}",
            **extra,
        }
    )


def test_cc_by_article_is_ingested_with_full_provenance(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A recorded eLife article is stored, attributed to its sources, and approved."""
    report = ingest("PMC10718527", bucket)
    assert report.outcome == IngestOutcome.CREATED
    assert report.gate_status == GateStatus.APPROVED
    assert report.content_parsed

    paper = Paper.objects.get(pmcid="PMC10718527")
    assert (paper.doi, paper.pmid) == ("10.7554/elife.93719", "38088194")
    version = PaperVersion.objects.get(paper=paper)
    assert version.is_current
    assert (version.licence_family, version.licence_version) == ("cc-by", "4.0")
    assert version.decision_source == "pmc:license_code"
    assert version.title == "Getting bacterial cells into shape"
    assert version.journal_title == "eLife"
    assert version.parser_version == PARSER_VERSION
    assert version.content_state == ContentState.PARSED
    assert version.content_md5 == "cac06beeb774deb26c2cb3b1ea0f5c60"

    # The licence code and the JATS licence are both recorded, with source and date.
    code = LicenceRecord.objects.get(version=version, field="pmc:license_code")
    assert (code.raw_value, code.source_url, code.retrieved_at) == (
        "CC BY",
        version.metadata_url,
        NOW,
    )
    jats = LicenceRecord.objects.filter(version=version, field="jats:ali:license_ref").get()
    assert jats.specific_use == "textmining"
    assert jats.source_url == version.content_url
    assert jats.block is not None
    assert jats.block.scope == "article"

    # Content matches rbcore's parse, and the access layer serves it.
    parsed = parse_jats(RECORDED_XML["PMC10718527.1"].read_bytes())
    expected_ids = [
        p.id
        for root in (*parsed.abstracts, parsed.body, parsed.back)
        for p in root.iter_paragraphs()
    ]
    assert (
        list(access.displayable_paragraphs(version).values_list("stable_id", flat=True))
        == expected_ids
    )
    assert access.displayable_version(paper) == version
    assert not LicenceReview.objects.exists()


def test_rerun_is_idempotent_and_does_not_refetch_xml(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A second run changes nothing, re-confirms the licence, and skips the XML."""
    # Arrange: one ingestion, and the row counts it produced.
    ingest("PMC10718527", bucket)
    counts = (
        Paragraph.objects.count(),
        LicenceRecord.objects.count(),
        PermissionsBlockRecord.objects.count(),
    )
    later = NOW + timedelta(days=8)

    # Act: re-check eight days later with nothing changed upstream.
    report = ingest("PMC10718527", bucket, now=later)
    assert report.outcome == IngestOutcome.UNCHANGED
    assert not report.content_parsed
    assert len(recorded.fetched(".xml")) == 1
    assert counts == (
        Paragraph.objects.count(),
        LicenceRecord.objects.count(),
        PermissionsBlockRecord.objects.count(),
    )

    # The licence code is re-confirmed, not rewritten, and the check time advances.
    code = LicenceRecord.objects.get(field="pmc:license_code")
    assert (code.retrieved_at, code.last_confirmed_at) == (NOW, later)
    assert PaperVersion.objects.get().last_checked_at == later


def test_tdm_manuscript_is_rejected_and_its_text_never_downloaded(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """TDM is refused outright: no XML request, no content, no review."""
    # Act: ingest the recorded TDM author manuscript.
    report = ingest("PMC13641010", bucket)
    assert (report.outcome, report.gate_status, report.licence_family) == (
        IngestOutcome.CREATED,
        GateStatus.REJECTED,
        "tdm",
    )

    # Nothing of the text was requested or stored, and nothing is queued for review.
    assert recorded.fetched(".xml") == []
    version = PaperVersion.objects.get()
    assert version.content_state == ContentState.SKIPPED
    assert version.is_manuscript is True
    assert not Paragraph.objects.exists()
    assert not LicenceReview.objects.exists()
    assert not Paper.objects.displayable().exists()


def test_figure_with_panel_licences_is_held_back_but_the_paper_is_shown(bucket: PmcBucket) -> None:
    """ELife 65180: Figure 1's panel-level blocks send it to review; the rest is displayable."""
    report = ingest("PMC7853715", bucket)
    assert report.gate_status == GateStatus.APPROVED
    version = PaperVersion.objects.get()
    figure1 = Figure.objects.get(version=version, stable_id="fig1")
    assert figure1.gate_status == GateStatus.REVIEW
    assert figure1 not in access.displayable_figures(version)
    assert LicenceReview.objects.filter(scope=ReviewScope.FIGURE, figure=figure1).count() == 1
    others = Figure.objects.filter(version=version).exclude(pk=figure1.pk)
    assert set(access.displayable_figures(version)) == set(others)


def test_figure_with_prose_only_licence_is_held_back(bucket: PmcBucket) -> None:
    """ELife 61907: Figure 1 is "not covered by the CC-BY licence"; it is never displayable."""
    ingest("PMC7781593", bucket)
    version = PaperVersion.objects.get()
    figure1 = Figure.objects.get(version=version, stable_id="fig1")
    assert not Figure.objects.displayable().filter(pk=figure1.pk).exists()
    assert not Figure.objects.rewriteable().filter(pk=figure1.pk).exists()
    review = LicenceReview.objects.get(figure=figure1)
    assert "without a machine-readable licence" in review.reasons[0]
    assert Figure.objects.displayable().filter(version=version, kind="table").exists()


def test_plos_article_arrives_through_pmc(bucket: PmcBucket) -> None:
    """PLOS papers are deposited in PMC and ingested from there like any other."""
    report = ingest("PMC11964404", bucket)
    assert report.gate_status == GateStatus.APPROVED
    version = PaperVersion.objects.get()
    assert "PLOS" in version.journal_title.upper()
    assert version.paper.doi == "10.1371/journal.pmed.1004542"
    assert Paper.objects.rewriteable().get() == version.paper


def test_article_not_in_bucket_creates_nothing(bucket: PmcBucket) -> None:
    """An ID that ESearch knows but the bucket does not yet hold is reported, not stored."""
    report = ingest("PMC900000999", bucket)
    assert report.outcome == IngestOutcome.NOT_IN_BUCKET
    assert not Paper.objects.exists()


def test_article_removed_from_bucket_is_held_for_review_until_relisted(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A stored article the bucket stops listing stops being displayable and is re-checked."""
    ingest("PMC10718527", bucket)
    assert Paper.objects.displayable().exists()

    # The bucket now lists no version of it (a synthetic empty listing).
    recorded.add_listing("PMC10718527", [])
    later = NOW + timedelta(days=8)
    report = ingest("PMC10718527", bucket, now=later)
    assert (report.outcome, report.gate_status, report.version_id) == (
        IngestOutcome.WITHDRAWN,
        GateStatus.REVIEW,
        "PMC10718527.1",
    )
    version = PaperVersion.objects.get()
    assert (version.last_checked_at, version.source_withdrawn_at) == (later, later)
    assert not Paper.objects.displayable().exists()
    assert not Paragraph.objects.displayable().exists()
    review = LicenceReview.objects.get(scope=ReviewScope.VERSION)
    assert "no longer listed by the source" in " ".join(review.reasons)

    # Checking again keeps the first withdrawal time and the same single review.
    even_later = later + timedelta(days=8)
    ingest("PMC10718527", bucket, now=even_later)
    version.refresh_from_db()
    assert (version.last_checked_at, version.source_withdrawn_at) == (even_later, later)
    assert LicenceReview.objects.filter(status="open").count() == 1

    # Listed again: the withdrawal is cleared and the automated decision returns.
    recorded.overrides.clear()
    report = ingest("PMC10718527", bucket, now=even_later + timedelta(days=1))
    assert (report.outcome, report.gate_status) == (IngestOutcome.UPDATED, GateStatus.APPROVED)
    version.refresh_from_db()
    assert version.source_withdrawn_at is None
    assert Paper.objects.displayable().get() == version.paper
    assert not LicenceReview.objects.filter(status="open").exists()


def test_jats_rejection_removes_text_and_does_not_refetch_it(
    bucket: PmcBucket, recorded: RecordedBucket, fetcher: PoliteFetcher
) -> None:
    """No code plus an all-rights-reserved JATS licence: rejected, and no text is kept."""
    # A synthetic article without a PMC code whose JATS licence reserves all rights.
    serve_synthetic(
        recorded,
        version=1,
        xml=synthetic_jats(["Synthetic reserved text."], licence="all-rights-reserved"),
        code=None,
    )
    report = ingest(SYNTHETIC_PMCID, bucket)
    assert (report.gate_status, report.licence_family) == (
        GateStatus.REJECTED,
        "all-rights-reserved",
    )
    version = PaperVersion.objects.get()
    assert version.content_state == ContentState.REMOVED
    assert not Paragraph.objects.exists()
    assert PermissionsBlockRecord.objects.active().filter(scope="article").count() == 1

    # Neither the database nor the download cache keeps the rejected XML.
    cached = fetcher.cache_path(version.content_url)
    assert cached is not None
    assert not cached.exists()

    # A re-check with the same XML keeps the rejection without parsing the text again.
    report = ingest(SYNTHETIC_PMCID, bucket, now=NOW + timedelta(days=8))
    assert (report.outcome, report.gate_status, report.content_parsed) == (
        IngestOutcome.UNCHANGED,
        GateStatus.REJECTED,
        False,
    )
    assert not Paragraph.objects.exists()


def test_reviewer_rejection_removes_text_and_new_evidence_brings_it_back(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """Text removed after a review rejection is fetched again once new evidence approves it.

    A reviewer approving a removed version instead is covered in test_receivers.py.
    """
    # The code and the JATS disagree (synthetic CC BY-ND code), so the version is reviewed.
    recorded.add_metadata({**recorded_metadata("PMC10718527.1"), "license_code": "CC BY-ND"})
    ingest("PMC10718527", bucket)
    review = LicenceReview.objects.get(scope=ReviewScope.VERSION, status="open")
    assert Paragraph.objects.exists()

    # Rejecting removes the text; the evidence stays, so a re-check stays rejected.
    resolve_review(review, approve=False, licence_value="", note="Synthetic test.", reviewer=None)
    assert PaperVersion.objects.get().content_state == ContentState.REMOVED
    assert not Paragraph.objects.exists()
    report = ingest("PMC10718527", bucket, now=NOW + timedelta(days=8))
    assert (report.gate_status, report.content_parsed) == (GateStatus.REJECTED, False)

    # New evidence (the code now agrees with the JATS) re-opens the question: the
    # automated decision approves, so the text is fetched again in the same run.
    recorded.add_metadata(recorded_metadata("PMC10718527.1"))
    report = ingest("PMC10718527", bucket, now=NOW + timedelta(days=9))
    assert (report.gate_status, report.content_parsed) == (GateStatus.APPROVED, True)
    assert PaperVersion.objects.get().content_state == ContentState.PARSED
    assert Paragraph.objects.displayable().exists()


def test_crash_before_the_gate_leaves_evidence_and_decision_consistent(
    bucket: PmcBucket, recorded: RecordedBucket, monkeypatch: pytest.MonkeyPatch
) -> None:
    """New licence evidence and the decision drawn from it commit together or not at all."""
    ingest("PMC10718527", bucket)
    recorded.add_metadata({**recorded_metadata("PMC10718527.1"), "license_code": "CC BY-ND"})

    def crash(*args: object, **kwargs: object) -> None:
        """Simulate the worker dying before the gate is recomputed."""
        raise RuntimeError("synthetic crash")

    # The run dies after writing the new code but before the gate runs.
    monkeypatch.setattr(pipeline, "evaluate_version", crash)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        ingest("PMC10718527", bucket, now=NOW + timedelta(days=1))

    # Nothing of that run is stored: the old code and the old decision still match.
    code = LicenceRecord.objects.active().get(field="pmc:license_code")
    assert code.raw_value == "CC BY"
    assert LicenceRecord.objects.filter(field="pmc:license_code").count() == 1
    assert PaperVersion.objects.get().gate_status == GateStatus.APPROVED

    # The next run applies the new evidence and its decision together.
    monkeypatch.undo()
    report = ingest("PMC10718527", bucket, now=NOW + timedelta(days=2))
    assert report.gate_status == GateStatus.REVIEW
    assert not Paper.objects.displayable().exists()


def test_retraction_is_recorded_blocks_rewriting_and_can_be_withdrawn(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A (synthetic) is_retracted flag keeps the paper readable but never rewriteable."""
    # Arrange: the recorded article with a synthetic is_retracted flag.
    metadata = recorded_metadata("PMC10718527.1")
    recorded.add_metadata({**metadata, "is_retracted": True})
    ingest("PMC10718527", bucket)

    # The retraction is recorded with its source; the paper is readable, not rewriteable.
    paper = Paper.objects.get()
    assert (paper.is_retracted, paper.retraction_source, paper.retraction_recorded_at) == (
        True,
        "pmc:is_retracted",
        NOW,
    )
    assert Paper.objects.displayable().filter(pk=paper.pk).exists()
    assert not Paper.objects.rewriteable().exists()
    assert not Paragraph.objects.rewriteable().exists()

    # The read API hands every reader path the notice it must show.
    assert access.retraction_notice(paper) == access.RetractionNotice(
        source="pmc:is_retracted", retraction_date=None, recorded_at=NOW
    )

    # PMC clears the flag: so do we, because PMC set it, and the notice goes.
    recorded.add_metadata(metadata)
    ingest("PMC10718527", bucket)
    paper.refresh_from_db()
    assert not paper.is_retracted
    assert access.retraction_notice(paper) is None
    assert Paper.objects.rewriteable().filter(pk=paper.pk).exists()


def test_licence_code_change_supersedes_the_old_record(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A changed code is a new record; the old one is kept as superseded history."""
    ingest("PMC10718527", bucket)
    metadata = recorded_metadata("PMC10718527.1")
    recorded.add_metadata({**metadata, "license_code": "CC BY-ND"})
    later = NOW + timedelta(days=1)

    report = ingest("PMC10718527", bucket, now=later)
    assert report.outcome == IngestOutcome.UPDATED
    codes = LicenceRecord.objects.filter(field="pmc:license_code").order_by("retrieved_at")
    assert [(c.raw_value, c.superseded_at) for c in codes] == [("CC BY", later), ("CC BY-ND", None)]
    # The JATS still says CC BY, so the sources now disagree: review, nothing shown.
    assert report.gate_status == GateStatus.REVIEW
    assert not Paper.objects.displayable().exists()


def test_code_turning_tdm_purges_stored_text(bucket: PmcBucket, recorded: RecordedBucket) -> None:
    """If the source later says TDM, stored full text is removed and the paper rejected."""
    ingest("PMC10718527", bucket)
    recorded.add_metadata({**recorded_metadata("PMC10718527.1"), "license_code": "TDM"})
    report = ingest("PMC10718527", bucket, now=NOW + timedelta(days=1))
    assert report.gate_status == GateStatus.REJECTED
    assert not Paragraph.objects.exists()
    assert PaperVersion.objects.get().content_state == ContentState.SKIPPED
    assert not PermissionsBlockRecord.objects.active().exists()
    assert PermissionsBlockRecord.objects.exists(), "superseded provenance is kept"


def test_new_version_becomes_current(bucket: PmcBucket, recorded: RecordedBucket) -> None:
    """When a new version appears, it replaces the old one as the version served."""
    # Arrange: version 1 is ingested, then the bucket lists version 2 as well.
    serve_synthetic(recorded, version=1, xml=synthetic_jats(["Synthetic version one."]))
    ingest(SYNTHETIC_PMCID, bucket)
    serve_synthetic(
        recorded, version=2, xml=synthetic_jats(["Synthetic version two."]), listed=[1, 2]
    )
    report = ingest(SYNTHETIC_PMCID, bucket)

    # Version 2 is now the only current version, and only its text is served.
    assert report.version_id == f"{SYNTHETIC_PMCID}.2"
    v1, v2 = PaperVersion.objects.order_by("version_number")
    assert (v1.is_current, v2.is_current) == (False, True)
    assert access.displayable_version(v2.paper) == v2
    assert list(Paragraph.objects.displayable().values_list("text", flat=True)) == [
        "Synthetic version two."
    ]


def test_changed_xml_reparses_and_keeps_surviving_paragraphs(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """An updated XML keeps paragraph rows (and annotations) whose stable IDs survive."""
    # Arrange: a synthetic article with two paragraphs and an annotation on the first.
    serve_synthetic(
        recorded, version=1, xml=synthetic_jats(["Synthetic alpha text.", "Synthetic beta."])
    )
    ingest(SYNTHETIC_PMCID, bucket)
    first = Paragraph.objects.get(stable_id="body-p1")
    annotation = Annotation.objects.create(
        paper_version=first.version,
        paragraph=first,
        target={
            "source": first.version.source_version_id,
            "selector": [
                {"type": "TextQuoteSelector", "exact": "alpha"},
                {"type": "TextPositionSelector", "start": 10, "end": 15},
            ],
        },
        body={"type": "TextualBody", "value": "Synthetic explanation (test only)."},
        provenance=Provenance.HUMAN,
    )

    # Act: the same version's XML changes; the second paragraph disappears.
    serve_synthetic(recorded, version=1, xml=synthetic_jats(["Synthetic alpha text, edited."]))
    report = ingest(SYNTHETIC_PMCID, bucket, now=NOW + timedelta(days=1))

    # The surviving paragraph keeps its row, so the annotation stays attached.
    assert report.content_parsed
    assert list(Paragraph.objects.values_list("pk", "text")) == [
        (first.pk, "Synthetic alpha text, edited.")
    ]
    annotation.refresh_from_db()
    assert annotation.paragraph_id == first.pk
    assert annotation.paragraph_text_sha256 != Paragraph.objects.get().text_sha256, (
        "drift is detectable"
    )


def test_unparseable_xml_goes_to_review(bucket: PmcBucket, recorded: RecordedBucket) -> None:
    """Malformed XML is recorded as a failure and the paper waits for a human."""
    serve_synthetic(recorded, version=1, xml=b"<article><unclosed></article>")
    report = ingest(SYNTHETIC_PMCID, bucket)
    assert report.gate_status == GateStatus.REVIEW
    version = PaperVersion.objects.get()
    assert version.content_state == ContentState.FAILED
    assert version.content_error.startswith("JATS parse error")


def test_missing_xml_raises_for_retry_and_leaves_paper_pending(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A failed download raises (the worker retries) and nothing becomes displayable."""
    serve_synthetic(recorded, version=1, xml=synthetic_jats(["Synthetic."]))
    recorded.overrides = {
        k: v for k, v in recorded.overrides.items() if not k.split("?")[0].endswith(".xml")
    }
    with pytest.raises(FetchError):
        ingest(SYNTHETIC_PMCID, bucket)
    version = PaperVersion.objects.get()
    assert version.content_state == ContentState.NONE
    assert not version.can_display


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.7554/eLife.93719", "10.7554/elife.93719"),
        ("https://doi.org/10.1/ABC", "10.1/abc"),
        ("doi:10.1/x", "10.1/x"),
        ("", None),
        (None, None),
    ],
)
def test_normalise_doi(value: str | None, expected: str | None) -> None:
    """DOIs are stored bare and lower-cased."""
    assert normalise_doi(value) == expected


def test_doi_already_held_by_another_paper_is_not_taken(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """Two PMC records with one DOI never merge silently; the second keeps no DOI."""
    Paper.objects.create(pmcid="PMC900000777", doi="10.9999/synthetic.1")
    serve_synthetic(recorded, version=1, xml=synthetic_jats(["Synthetic."]))
    ingest(SYNTHETIC_PMCID, bucket)
    assert Paper.objects.get(pmcid=SYNTHETIC_PMCID).doi is None
