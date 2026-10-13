"""POST /api/v1/lookup/ and GET /api/v1/lookup/requests/<id>/ (entry point 2)."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.db import connection
from django.test import override_settings
from metadata_support import LANCET_DOI, PLOS_DOI, RecordedMetadata
from reader_support import ingest
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle
from support import RecordedBucket

from rb_backend.api import views
from rb_backend.discovery.models import LookupRequest
from rb_backend.ingestion.pmc import PmcBucket
from rb_backend.ingestion.tasks import job_status
from rbcore.http import FetchError

pytestmark = pytest.mark.django_db

PLOS_PMCID = "PMC11964404"
TDM_PMCID = "PMC13641010"


def post(api: APIClient, query: str) -> Any:
    """POST a lookup."""
    return api.post("/api/v1/lookup/", {"query": query}, format="json")


def status_of(api: APIClient, request_id: str) -> Any:
    """GET a lookup request's status."""
    return api.get(f"/api/v1/lookup/requests/{request_id}/")


def set_job_status(job_id: int, status: str) -> None:
    """Simulate the worker moving a job to a status (read-only in Django, so SQL)."""
    with connection.cursor() as cursor:
        cursor.execute("UPDATE procrastinate_jobs SET status = %s WHERE id = %s", [status, job_id])


def test_eligible_paper_is_queued_then_ready(api: APIClient, bucket: PmcBucket) -> None:
    """A CC BY PMC paper not yet stored is queued; once ingested its status is ready."""
    response = post(api, PLOS_DOI)
    assert response.status_code == 202
    data = response.json()
    assert data["outcome"] == "queued"
    assert data["identifier"] == {"kind": "doi", "value": PLOS_DOI}
    request = data["request"]
    assert request["status"] == "preparing"
    assert request["pmcid"] == PLOS_PMCID

    # The request and its worker job exist.
    stored = LookupRequest.objects.get()
    assert (stored.pmcid, stored.licence_code, stored.doi) == (PLOS_PMCID, "CC BY", PLOS_DOI)
    assert stored.job_id is not None
    assert job_status(stored.job_id) == "todo"

    # The worker ingests it (run inline here); the status then points at the paper.
    ingest(PLOS_PMCID, bucket)
    ready = status_of(api, request["id"]).json()
    assert ready["status"] == "ready"
    assert ready["paper"]["key"] == PLOS_PMCID


def test_repeat_lookup_reuses_the_waiting_request(api: APIClient) -> None:
    """A second lookup while the job waits returns the same request, not a new job."""
    first = post(api, PLOS_DOI).json()["request"]["id"]
    second = post(api, PLOS_PMCID).json()
    assert second["outcome"] == "queued"
    assert second["request"]["id"] == first
    assert LookupRequest.objects.count() == 1


def test_paper_already_in_the_corpus(api: APIClient, bucket: PmcBucket) -> None:
    """Identifiers of a corpus paper go straight to it, without any network request."""
    ingest(PLOS_PMCID, bucket)
    for query in (PLOS_DOI, f"https://doi.org/{PLOS_DOI}", PLOS_PMCID, "40173335"):
        data = post(api, query).json()
        assert data["outcome"] == "in_corpus", query
        assert data["paper"]["key"] == PLOS_PMCID
    assert LookupRequest.objects.count() == 0


def test_author_manuscript_is_refused_at_the_primary_source(
    api: APIClient, recorded: RecordedBucket
) -> None:
    """A TDM licence code is not eligible: nothing is queued and the XML is never fetched."""
    data = post(api, TDM_PMCID).json()
    assert data["outcome"] == "not_available"
    assert data["licence_code"] == "TDM"
    assert "licence does not allow" in data["message"]
    assert LookupRequest.objects.count() == 0
    assert recorded.fetched(".xml") == []


def test_stored_rejected_paper_is_not_rechecked(
    api: APIClient, bucket: PmcBucket, recorded: RecordedBucket
) -> None:
    """A paper the gate already rejected is reported without asking the bucket again."""
    ingest(TDM_PMCID, bucket)
    before = len(recorded.requests)
    data = post(api, TDM_PMCID).json()
    assert data["outcome"] == "not_available"
    assert len(recorded.requests) == before


def test_paper_not_in_pmc_links_to_the_doi(api: APIClient) -> None:
    """The retracted Lancet paper is not in PMC: "not available here", with its DOI link."""
    data = post(api, LANCET_DOI).json()
    assert data["outcome"] == "not_available"
    assert data["links"]["doi"] == "https://doi.org/10.1016/s0140-6736(97)11096-0"
    assert data["links"]["scholar"].startswith("https://scholar.google.com/scholar?q=")


def test_arxiv_ids_are_not_ingested_yet(
    api: APIClient, recorded: RecordedBucket, recorded_metadata: RecordedMetadata
) -> None:
    """ArXiv IDs get links to arXiv and its DOI, and no request is made."""
    data = post(api, "arXiv:2310.06825").json()
    assert data["outcome"] == "not_available"
    assert data["links"]["arxiv"] == "https://arxiv.org/abs/2310.06825"
    assert data["links"]["doi"] == "https://doi.org/10.48550/arxiv.2310.06825"
    assert recorded.requests == recorded_metadata.requests == []


def test_titles_list_candidates(api: APIClient, bucket: PmcBucket) -> None:
    """A title is never guessed: matching papers are listed for the reader to choose."""
    ingest(PLOS_PMCID, bucket)
    data = post(api, "predatory journals").json()
    assert data["outcome"] == "candidates"
    assert data["search"]["corpus"]["results"][0]["key"] == PLOS_PMCID
    assert data["search"]["openalex"]["status"] == "ok"


@override_settings(RB_LOOKUP_DAILY_INGEST_LIMIT=0)
def test_daily_budget(api: APIClient) -> None:
    """Once today's budget is spent, eligible papers are not queued."""
    data = post(api, PLOS_DOI).json()
    assert data["outcome"] == "budget_exhausted"
    assert LookupRequest.objects.count() == 0


def test_unreachable_bucket_is_503(api: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """If the primary source cannot be reached, the reader is told to try again."""

    def broken_bucket() -> PmcBucket:
        """Fail like an unreachable bucket."""
        raise FetchError("synthetic outage")

    monkeypatch.setattr(views, "pmc_bucket", broken_bucket)
    response = post(api, PLOS_DOI)
    assert response.status_code == 503
    assert response.json()["outcome"] == "unavailable"


def test_unreachable_id_converter_is_503(
    api: APIClient, recorded_metadata: RecordedMetadata
) -> None:
    """If the ID converter fails with nothing cached, the lookup is unavailable."""
    recorded_metadata.host_overrides["pmc.ncbi.nlm.nih.gov"] = (500, b"")
    response = post(api, PLOS_DOI)
    assert response.status_code == 503


@pytest.mark.parametrize("body", [{}, {"query": ""}, {"query": "ab"}])
def test_unusable_queries_are_400(api: APIClient, body: dict[str, str]) -> None:
    """Missing, empty and too-short queries are refused."""
    assert api.post("/api/v1/lookup/", body, format="json").status_code == 400


def test_failed_job_is_reported(api: APIClient) -> None:
    """A job the worker gave up on shows as failed."""
    request = post(api, PLOS_DOI).json()["request"]
    job_id = LookupRequest.objects.get().job_id
    assert job_id is not None
    set_job_status(job_id, "failed")
    assert status_of(api, request["id"]).json()["status"] == "failed"


def test_held_for_review(api: APIClient, bucket: PmcBucket) -> None:
    """A stored version the gate sent to review is "held", not ready."""
    request = post(api, PLOS_DOI).json()["request"]
    job_id = LookupRequest.objects.get().job_id
    assert job_id is not None
    ingest(PLOS_PMCID, bucket)
    set_job_status(job_id, "succeeded")
    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE corpus_paperversion SET gate_status = 'review', can_display = false, "
            "can_rewrite = false, output_licence_family = '', output_licence_version = ''"
        )
    assert status_of(api, request["id"]).json()["status"] == "held_for_review"


def test_unknown_request_is_404(api: APIClient) -> None:
    """Status of a request that does not exist."""
    assert status_of(api, str(uuid.uuid4())).status_code == 404


def test_lookups_are_rate_limited(api: APIClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Past the lookup rate, requests get 429."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "lookup", "2/min")
    codes = [post(api, "arXiv:2310.06825").status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_rate_limit_uses_the_socket_address_by_default(
    api: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spoofed X-Forwarded-For does not reset the limit (no trusted proxies by default)."""
    monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, "lookup", "1/min")
    first = api.post(
        "/api/v1/lookup/",
        {"query": "arXiv:2310.06825"},
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.1",
    )
    second = api.post(
        "/api/v1/lookup/",
        {"query": "arXiv:2310.06825"},
        format="json",
        HTTP_X_FORWARDED_FOR="203.0.113.2",
    )
    assert (first.status_code, second.status_code) == (200, 429)


def test_lookup_requests_store_nothing_about_the_reader(api: APIClient) -> None:
    """Only the query, the article and the job are stored."""
    post(api, PLOS_DOI)
    fields = {f.name for f in LookupRequest._meta.get_fields()}
    assert fields == {"id", "query", "pmcid", "doi", "licence_code", "job_id", "created_at"}


def test_bucket_listing_without_versions_is_not_in_pmc(
    api: APIClient, recorded: RecordedBucket
) -> None:
    """An ID the converter maps to a PMC ID the bucket does not list is "not in PMC"."""
    # A synthetic empty listing: the bucket has no version of the article.
    recorded.add_listing(PLOS_PMCID, [])
    data = post(api, PLOS_DOI).json()
    assert data["outcome"] == "not_available"
    assert "not in PubMed Central" in data["message"]
