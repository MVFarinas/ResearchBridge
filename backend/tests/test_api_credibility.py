"""GET /api/v1/papers/<key>/credibility/: neutral, paper-level signals with "as of" dates."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from django.utils import timezone
from metadata_support import KARGER_DOI, LANCET_DOI, RecordedMetadata
from reader_support import ingest
from rest_framework.test import APIClient

from rb_backend.corpus import access
from rb_backend.corpus.models import Paper
from rb_backend.corpus.retractions import record_external_retraction
from rb_backend.ingestion.pmc import PmcBucket
from rb_backend.metadata.credibility import paper_credibility
from rb_backend.metadata.models import CachedResponse
from rb_backend.metadata.services import MetadataClients

pytestmark = pytest.mark.django_db

PLOS = "PMC11964404"


def credibility(api: APIClient, key: str = PLOS) -> Any:
    """GET a paper's credibility signals."""
    return api.get(f"/api/v1/papers/{key}/credibility/")


def test_signals_from_all_three_sources(api: APIClient, bucket: PmcBucket) -> None:
    """OpenAlex metrics, iCite citations and Crossref notices, each with its date and source."""
    ingest(PLOS, bucket)
    response = credibility(api)
    assert response.status_code == 200
    data = response.json()
    for section in ("openalex", "icite", "crossref"):
        assert data[section]["status"] == "ok", section
        assert data[section]["as_of"] is not None
        assert data[section]["source"]["name"]
    assert data["openalex"]["metrics"]["is_retracted"] is False
    assert data["icite"]["metrics"]["citations_by_year"] == [
        {"year": 2025, "count": 1},
        {"year": 2026, "count": 3},
    ]
    assert data["crossref"]["notices"] == []
    assert data["integrity"] == {
        "retracted": False,
        "retraction_source": None,
        "retraction_date": None,
        "expression_of_concern": False,
        "corrected": False,
    }


def test_no_journal_level_signals(api: APIClient, bucket: PmcBucket) -> None:
    """Nothing about the journal or publisher is returned (decisions.md §2.3 deferred)."""
    ingest(PLOS, bucket)
    text = str(credibility(api).json()).lower()
    for journal_signal in ("listed_in", "is_in_doaj", "h_index", "2yr_mean", "is_core", "sjr"):
        assert journal_signal not in text


def test_answers_are_cached(
    api: APIClient, bucket: PmcBucket, recorded_metadata: RecordedMetadata
) -> None:
    """A second request is served from the cache with the same "as of" date."""
    ingest(PLOS, bucket)
    first = credibility(api).json()
    count = len(recorded_metadata.requests)
    second = credibility(api).json()
    assert len(recorded_metadata.requests) == count == 3
    assert first["openalex"]["as_of"] == second["openalex"]["as_of"]


def test_unavailable_source_is_reported_not_hidden(
    api: APIClient, bucket: PmcBucket, recorded_metadata: RecordedMetadata
) -> None:
    """With iCite down and nothing cached, that section says so and the rest still works."""
    ingest(PLOS, bucket)
    recorded_metadata.host_overrides["icite.od.nih.gov"] = (503, b"")
    data = credibility(api).json()
    assert data["icite"]["status"] == "unavailable"
    assert data["icite"]["metrics"] is None
    assert data["openalex"]["status"] == "ok"


def test_stale_answer_is_served_when_refresh_fails(
    api: APIClient, bucket: PmcBucket, recorded_metadata: RecordedMetadata
) -> None:
    """After expiry, a failed refresh serves the old answer flagged stale."""
    ingest(PLOS, bucket)
    first = credibility(api).json()
    CachedResponse.objects.update(fetched_at=timezone.now() - timedelta(days=30))
    recorded_metadata.host_overrides["api.openalex.org"] = (500, b"")
    data = credibility(api).json()
    assert data["openalex"]["status"] == "ok"
    assert data["openalex"]["stale"] is True
    assert data["openalex"]["metrics"] == first["openalex"]["metrics"]
    assert "refresh failed" in data["openalex"]["message"]


def _synthetic_paper(doi: str) -> Paper:
    """A synthetic paper row carrying a real DOI, to look its metadata up (no content)."""
    return Paper.objects.create(pmcid="PMC900000401", doi=doi)


def test_crossref_retraction_is_recorded_on_the_paper(clients: MetadataClients) -> None:
    """The Lancet retraction notice marks the paper retracted, so it is never rewritten."""
    paper = _synthetic_paper(LANCET_DOI)
    data = paper_credibility(paper, clients)
    paper.refresh_from_db()
    assert paper.is_retracted is True
    assert paper.retraction_source == "crossref:retraction-watch"
    assert paper.retraction_date == date(2010, 2, 6)
    assert data["integrity"]["retracted"] is True
    assert data["integrity"]["corrected"] is True
    assert [n["kind"] for n in data["crossref"]["notices"]] == ["correction", "retraction"]
    assert data["crossref"]["notices"][1]["notice_url"] == (
        "https://doi.org/10.1016/s0140-6736(10)60175-4"
    )
    assert not access.rewriteable_papers().filter(pk=paper.pk).exists()


def test_expression_of_concern(clients: MetadataClients) -> None:
    """The Karger paper has an expression of concern (and a later retraction)."""
    paper = _synthetic_paper(KARGER_DOI)
    data = paper_credibility(paper, clients)
    assert data["integrity"]["expression_of_concern"] is True
    assert data["integrity"]["retracted"] is True


def test_sources_needing_missing_identifiers_are_not_applicable(
    clients: MetadataClients, recorded_metadata: RecordedMetadata
) -> None:
    """Without a DOI or PMID nothing is requested and each section says why."""
    paper = Paper.objects.create(pmcid="PMC900000402")
    data = paper_credibility(paper, clients)
    assert {data[s]["status"] for s in ("openalex", "icite", "crossref")} == {"not_applicable"}
    assert recorded_metadata.requests == []


def test_not_found_is_distinct_from_unavailable(clients: MetadataClients) -> None:
    """Sources with no record of the paper say so (404 on the fake host)."""
    paper = Paper.objects.create(pmcid="PMC900000403", doi="10.9999/synthetic.unknown")
    data = paper_credibility(paper, clients)
    assert data["openalex"]["status"] == "not_found"
    assert data["crossref"]["status"] == "not_found"
    assert "no record" in data["openalex"]["message"]


def test_first_retraction_source_is_kept() -> None:
    """A later source does not overwrite the first; it may fill a missing date."""
    paper = Paper.objects.create(pmcid="PMC900000404")
    now = timezone.now()
    assert record_external_retraction(
        paper, source="openalex:is_retracted", retraction_date=None, now=now
    )
    assert record_external_retraction(
        paper, source="crossref:publisher", retraction_date=date(2020, 1, 1), now=now
    )
    assert not record_external_retraction(
        paper, source="crossref:publisher", retraction_date=date(2021, 1, 1), now=now
    )
    paper.refresh_from_db()
    assert (paper.retraction_source, paper.retraction_date) == (
        "openalex:is_retracted",
        date(2020, 1, 1),
    )


def test_unknown_paper_is_404(api: APIClient) -> None:
    """Credibility is only served for displayable corpus papers."""
    assert credibility(api, "PMC999999999").status_code == 404
