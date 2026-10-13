"""GET /api/v1/search/: corpus and OpenAlex results, tags, degradation and validation."""

from __future__ import annotations

import json
from typing import Any

import pytest
from metadata_support import PLOS_DOI, RecordedMetadata, recorded_body
from reader_support import CC_BY_ND, ingest, serve_synthetic_article
from rest_framework.test import APIClient
from support import RecordedBucket

from rb_backend.discovery.availability import Availability, external_availability
from rb_backend.ingestion.pmc import PmcBucket
from rb_backend.metadata.models import CachedResponse, CacheSource
from rb_backend.metadata.openalex import SearchRequest
from rb_backend.metadata.services import MetadataClients

pytestmark = pytest.mark.django_db


def search(api: APIClient, **params: Any) -> Any:
    """GET the search endpoint."""
    return api.get("/api/v1/search/", params)


def test_corpus_and_openalex_results_together(api: APIClient, bucket: PmcBucket) -> None:
    """The recorded PLOS paper is found in the corpus; OpenAlex adds the wider record."""
    ingest("PMC11964404", bucket)
    data = search(api, q="predatory journals").json()
    [hit] = data["corpus"]["results"]
    assert hit["key"] == "PMC11964404"
    assert hit["availability"] == Availability.PLAIN_ENGLISH
    assert hit["rewrite_status"] == "not_generated"
    assert hit["licence"] == "CC BY 4.0"
    openalex = data["openalex"]
    assert openalex["status"] == "ok"
    assert openalex["as_of"] is not None
    assert openalex["total"] == 139874
    assert len(openalex["results"]) == 10


def test_openalex_results_are_tagged_from_its_licence_field(
    api: APIClient, bucket: PmcBucket
) -> None:
    """Outside the corpus: an open licence routes to lookup, otherwise "elsewhere"."""
    results = search(api, q="predatory journals").json()["openalex"]["results"]
    by_doi = {r["doi"]: r for r in results}
    # No licence reported: read it at the publisher.
    assert by_doi["10.1002/asi.23265"]["availability"] == Availability.ELSEWHERE
    assert by_doi["10.1002/asi.23265"]["lookup_query"] is None
    # A CC licence reported by OpenAlex: "may be available", routed to lookup by DOI.
    assert by_doi["10.1111/jdv.15039"]["availability"] == Availability.MAY_BE_AVAILABLE
    assert by_doi["10.1111/jdv.15039"]["lookup_query"] == "10.1111/jdv.15039"
    # "other-oa" is not an open licence.
    assert by_doi["10.1038/d41586-019-03759-y"]["availability"] == Availability.ELSEWHERE
    # Every result carries exactly one tag.
    assert all(r["availability"] in set(Availability) for r in results)


def test_openalex_work_in_the_corpus_takes_the_corpus_tag(
    api: APIClient,
    bucket: PmcBucket,
    recorded_metadata: RecordedMetadata,
    clients: MetadataClients,
) -> None:
    """A work OpenAlex returns that the corpus holds links to the corpus paper."""
    ingest("PMC11964404", bucket)
    # A synthetic one-result search wrapping the real recorded work record.
    work = json.loads(recorded_body("openalex-work-doi-10.1371-journal.pmed.1004542.json"))
    url = clients.openalex.search_url(SearchRequest(query="prey", per_page=10))
    recorded_metadata.url_overrides[url] = (
        200,
        json.dumps({"meta": {"count": 1}, "results": [work]}).encode(),
    )
    [result] = search(api, q="prey").json()["openalex"]["results"]
    assert result["key"] == "PMC11964404"
    assert result["doi"] == PLOS_DOI
    assert result["availability"] == Availability.PLAIN_ENGLISH
    assert result["licence_reported_by_openalex"] == "cc-by"


@pytest.mark.parametrize(
    ("status", "expected"), [(429, "refused"), (403, "refused"), (500, "unavailable")]
)
def test_openalex_failure_degrades_to_corpus_only(
    api: APIClient,
    bucket: PmcBucket,
    recorded_metadata: RecordedMetadata,
    status: int,
    expected: str,
) -> None:
    """When OpenAlex refuses or fails, corpus results still come back, with a notice."""
    ingest("PMC11964404", bucket)
    recorded_metadata.host_overrides["api.openalex.org"] = (status, b"{}")
    response = search(api, q="predatory journals")
    assert response.status_code == 200
    data = response.json()
    assert len(data["corpus"]["results"]) == 1
    assert data["openalex"]["status"] == expected
    assert "ResearchBridge only" in data["openalex"]["notice"]
    assert data["openalex"]["results"] == []


def test_openalex_answers_are_cached(api: APIClient, recorded_metadata: RecordedMetadata) -> None:
    """A repeated search is answered from the cache, keeping its "as of" date."""
    first = search(api, q="predatory journals").json()["openalex"]
    second = search(api, q="predatory journals").json()["openalex"]
    openalex_requests = [u for u in recorded_metadata.requests if "openalex" in u]
    assert len(openalex_requests) == 1
    assert first["as_of"] == second["as_of"]
    assert CachedResponse.objects.filter(source=CacheSource.OPENALEX_SEARCH).count() == 1


def test_openalex_can_be_skipped(api: APIClient, recorded_metadata: RecordedMetadata) -> None:
    """openalex=false searches the corpus only and makes no OpenAlex request."""
    data = search(api, q="sleep", openalex="false").json()
    assert data["openalex"]["status"] == "skipped"
    assert recorded_metadata.requests == []


def test_filters_reach_both_searches(
    api: APIClient,
    recorded: RecordedBucket,
    bucket: PmcBucket,
    recorded_metadata: RecordedMetadata,
) -> None:
    """Availability filters the corpus; years, types and sort reach OpenAlex."""
    serve_synthetic_article(recorded, pmcid="PMC900000301", title="Synthetic sleep study A")
    serve_synthetic_article(
        recorded,
        pmcid="PMC900000302",
        title="Synthetic sleep study B",
        licence_code="CC BY-ND",
        licence_url=CC_BY_ND,
    )
    for pmcid in ("PMC900000301", "PMC900000302"):
        ingest(pmcid, bucket)
    data = search(
        api,
        q="sleep",
        availability="original_annotations_only",
        year_from=2020,
        year_to=2025,
        type=["review", "article"],
        sort="newest",
    ).json()
    assert [r["key"] for r in data["corpus"]["results"]] == ["PMC900000302"]
    assert data["corpus"]["results"][0]["availability"] == Availability.ORIGINAL_ANNOTATIONS
    [openalex_url] = [u for u in recorded_metadata.requests if "openalex" in u]
    assert "publication_year%3A2020-2025%2Ctype%3Aarticle%7Creview" in openalex_url
    assert "sort=publication_date%3Adesc" in openalex_url


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"q": ""},
        {"q": "x", "year_from": 2024, "year_to": 2020},
        {"q": "x", "sort": "random"},
        {"q": "x", "page": 0},
        {"q": "x", "availability": "everything"},
        {"q": "x", "type": "book"},
    ],
)
def test_invalid_parameters_are_400(api: APIClient, params: dict[str, Any]) -> None:
    """Missing or out-of-range parameters are refused."""
    assert search(api, **params).status_code == 400


@pytest.mark.parametrize(
    ("licence", "has_id", "expected"),
    [
        ("cc-by", True, Availability.MAY_BE_AVAILABLE),
        ("cc-by-nc-nd", True, Availability.MAY_BE_AVAILABLE),
        ("cc0", True, Availability.MAY_BE_AVAILABLE),
        ("public-domain", True, Availability.MAY_BE_AVAILABLE),
        ("cc-by", False, Availability.ELSEWHERE),
        ("other-oa", True, Availability.ELSEWHERE),
        ("publisher-specific-oa", True, Availability.ELSEWHERE),
        (None, True, Availability.ELSEWHERE),
    ],
)
def test_external_availability(licence: str | None, has_id: bool, expected: Availability) -> None:
    """Only an open licence with an identifier lookup can check routes to lookup."""
    assert external_availability(openalex_licence=licence, has_lookup_id=has_id) == expected
