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
from rb_backend.ingestion.pipeline import (
    PARSER_VERSION,
    IngestOutcome,
    ingest_pmc_article,
    normalise_doi,
)
from rb_backend.ingestion.pmc import PmcBucket
from rbcore.http import FetchError
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
    code: str = "CC BY",
    listed: list[int] | None = None,
    **extra: Any,
) -> None:
    """Serve a synthetic article version: listing, metadata and XML with a matching MD5."""
    version_id = f"{SYNTHETIC_PMCID}.{version}"
    digest = recorded.add_xml(version_id, xml)
    recorded.add_listing(SYNTHETIC_PMCID, listed or [version])
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
    ingest("PMC10718527", bucket)
    counts = (
        Paragraph.objects.count(),
        LicenceRecord.objects.count(),
        PermissionsBlockRecord.objects.count(),
    )
    later = NOW + timedelta(days=8)

    report = ingest("PMC10718527", bucket, now=later)
    assert report.outcome == IngestOutcome.UNCHANGED
    assert not report.content_parsed
    assert len(recorded.fetched(".xml")) == 1
    assert counts == (
        Paragraph.objects.count(),
        LicenceRecord.objects.count(),
        PermissionsBlockRecord.objects.count(),
    )
    code = LicenceRecord.objects.get(field="pmc:license_code")
    assert (code.retrieved_at, code.last_confirmed_at) == (NOW, later)
    assert PaperVersion.objects.get().last_checked_at == later


def test_tdm_manuscript_is_rejected_and_its_text_never_downloaded(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """TDM is refused outright: no XML request, no content, no review."""
    report = ingest("PMC13641010", bucket)
    assert (report.outcome, report.gate_status, report.licence_family) == (
        IngestOutcome.CREATED,
        GateStatus.REJECTED,
        "tdm",
    )
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


def test_retraction_is_recorded_blocks_rewriting_and_can_be_withdrawn(
    bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A (synthetic) is_retracted flag keeps the paper readable but never rewriteable."""
    metadata = recorded_metadata("PMC10718527.1")
    recorded.add_metadata({**metadata, "is_retracted": True})
    ingest("PMC10718527", bucket)
    paper = Paper.objects.get()
    assert (paper.is_retracted, paper.retraction_source, paper.retraction_recorded_at) == (
        True,
        "pmc:is_retracted",
        NOW,
    )
    assert Paper.objects.displayable().filter(pk=paper.pk).exists()
    assert not Paper.objects.rewriteable().exists()
    assert not Paragraph.objects.rewriteable().exists()

    recorded.add_metadata(metadata)
    ingest("PMC10718527", bucket)
    paper.refresh_from_db()
    assert not paper.is_retracted
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
    serve_synthetic(recorded, version=1, xml=synthetic_jats(["Synthetic version one."]))
    ingest(SYNTHETIC_PMCID, bucket)
    serve_synthetic(
        recorded, version=2, xml=synthetic_jats(["Synthetic version two."]), listed=[1, 2]
    )
    report = ingest(SYNTHETIC_PMCID, bucket)

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

    serve_synthetic(recorded, version=1, xml=synthetic_jats(["Synthetic alpha text, edited."]))
    report = ingest(SYNTHETIC_PMCID, bucket, now=NOW + timedelta(days=1))
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
