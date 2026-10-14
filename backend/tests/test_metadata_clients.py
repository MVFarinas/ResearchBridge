"""The metadata clients against recorded responses (no network)."""

from __future__ import annotations

from datetime import date
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from metadata_support import (
    KARGER_DOI,
    LANCET_DOI,
    PLOS_DOI,
    PLOS_PMID,
    RecordedMetadata,
    make_clients,
)

from rb_backend.metadata.crossref import parse_notices
from rb_backend.metadata.errors import UpstreamError, UpstreamRefusedError
from rb_backend.metadata.fetch import build_metadata_fetcher, redact
from rb_backend.metadata.icite import parse_pub
from rb_backend.metadata.idconv import parse_record
from rb_backend.metadata.openalex import (
    OpenAlexClient,
    SearchRequest,
    parse_metrics,
    parse_work,
)
from rb_backend.metadata.services import MetadataClients

SYNTHETIC_KEY = "synthetic-test-key-not-real"


def test_openalex_work_metrics_from_recorded_response(clients: MetadataClients) -> None:
    """Citation count, yearly counts, FWCI, percentile and the retraction flag are read."""
    work = clients.openalex.work("doi", PLOS_DOI)
    assert work is not None
    metrics = parse_metrics(work)
    assert metrics.cited_by_count is not None
    assert metrics.cited_by_count >= 0
    # Years are sorted ascending and every count is an int.
    years = [item["year"] for item in metrics.counts_by_year]
    assert years == sorted(years)
    assert all(isinstance(item["count"], int) for item in metrics.counts_by_year)
    assert metrics.is_retracted is False


def test_openalex_reports_the_retracted_lancet_paper(clients: MetadataClients) -> None:
    """The recorded Lancet record is flagged retracted, with its metrics."""
    work = clients.openalex.work("doi", LANCET_DOI)
    metrics = parse_metrics(work)
    assert metrics.is_retracted is True
    assert metrics.cited_by_count == 3004
    assert metrics.fwci == pytest.approx(38.7867)


def test_openalex_unknown_work_is_none(clients: MetadataClients) -> None:
    """A 404 from OpenAlex means "no such work", not an error."""
    assert clients.openalex.work("doi", "10.9999/synthetic-unknown") is None


def test_openalex_work_trimming_keeps_only_used_fields(clients: MetadataClients) -> None:
    """Locations keep licence, OA flag and journal; authorships keep names only."""
    work = clients.openalex.work("doi", PLOS_DOI)
    assert work is not None
    assert set(work["primary_location"]) == {"license", "is_oa", "source"}
    assert work["primary_location"]["license"] == "cc-by"
    assert all(set(item) == {"author"} for item in work["authorships"])


def test_openalex_search_parses_results(clients: MetadataClients) -> None:
    """The recorded keyless search gives ten works with DOIs and licences."""
    answer = clients.openalex.search(SearchRequest(query="predatory journals"))
    works = [parse_work(item) for item in answer["results"]]
    assert answer["count"] == 139874
    assert len(works) == 10
    assert works[0].doi == "10.1002/asi.23265"
    assert works[1].licence == "cc-by"
    assert works[0].title


def test_search_url_has_filters_sort_and_no_key() -> None:
    """Year range, types and date sort map onto OpenAlex parameters."""
    clients = make_clients(RecordedMetadata(), openalex_key=SYNTHETIC_KEY)
    request = SearchRequest(
        query="sleep",
        year_from=2020,
        year_to=2024,
        work_types=("article", "review"),
        sort="newest",
        page=2,
    )
    params = parse_qs(urlsplit(clients.openalex.search_url(request)).query)
    assert params["filter"] == ["publication_year:2020-2024,type:article|review"]
    assert params["sort"] == ["publication_date:desc"]
    assert params["page"] == ["2"]
    # The canonical form (the cache key) never contains the key.
    assert SYNTHETIC_KEY not in request.canonical()
    assert "api_key" not in params


@pytest.mark.parametrize(
    ("year_from", "year_to", "expected"),
    [(2020, None, "publication_year:>2019"), (None, 2020, "publication_year:<2021")],
)
def test_open_ended_year_filters(year_from: int | None, year_to: int | None, expected: str) -> None:
    """Open-ended ranges use OpenAlex's > and < forms."""
    params = SearchRequest(query="x", year_from=year_from, year_to=year_to).params()
    assert params["filter"] == expected


def test_openalex_key_is_sent_but_redacted_from_errors() -> None:
    """With a key, requests carry it; a refusal's message never repeats it."""
    recorded = RecordedMetadata(host_overrides={"api.openalex.org": (403, b"{}")})
    clients = make_clients(recorded, openalex_key=SYNTHETIC_KEY)
    with pytest.raises(UpstreamRefusedError) as caught:
        clients.openalex.work("doi", PLOS_DOI)
    assert f"api_key={SYNTHETIC_KEY}" in recorded.requests[0]
    assert SYNTHETIC_KEY not in str(caught.value)
    assert caught.value.status == 403


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, UpstreamRefusedError),
        (429, UpstreamRefusedError),
        (500, UpstreamError),
        (503, UpstreamError),
    ],
)
def test_get_json_maps_statuses(status: int, error: type[Exception]) -> None:
    """Refusals and outages become distinct errors."""
    recorded = RecordedMetadata(host_overrides={"api.openalex.org": (status, b"")})
    clients = make_clients(recorded)
    with pytest.raises(error):
        clients.openalex.work("doi", PLOS_DOI)


def test_get_json_refuses_invalid_json() -> None:
    """A body that is not JSON is an upstream error (synthetic body)."""
    recorded = RecordedMetadata(host_overrides={"api.crossref.org": (200, b"<html>synthetic")})
    clients = make_clients(recorded)
    with pytest.raises(UpstreamError, match="not valid JSON"):
        clients.crossref.work(PLOS_DOI)


def test_redact_hides_every_secret() -> None:
    """Secrets are replaced; empty values are ignored."""
    assert redact("a=s1&b=s2", ["s1", None, "", "s2"]) == "a=[redacted]&b=[redacted]"


def test_icite_counts_citations_by_year(clients: MetadataClients) -> None:
    """Citing PMIDs are aggregated per year; a missing RCR stays None."""
    record = clients.icite.pub(PLOS_PMID)
    metrics = parse_pub(record)
    assert metrics.citation_count == 4
    assert metrics.citations_by_year == [{"year": 2025, "count": 1}, {"year": 2026, "count": 3}]
    assert metrics.relative_citation_ratio is None
    assert metrics.is_research_article is False


def test_icite_unknown_pmid_is_none(clients: MetadataClients) -> None:
    """An empty data list (here a 404 from the fake host) means no record."""
    assert clients.icite.pub("999999999") is None


def test_crossref_notices_for_the_retracted_lancet_paper(clients: MetadataClients) -> None:
    """A correction (2004) and the retraction (2010), both from Retraction Watch."""
    notices = parse_notices(clients.crossref.work(LANCET_DOI))
    assert [(n.kind, n.notice_date, n.source) for n in notices] == [
        ("correction", date(2004, 3, 6), "retraction-watch"),
        ("retraction", date(2010, 2, 6), "retraction-watch"),
    ]
    assert notices[1].is_retraction
    assert notices[0].is_correction
    assert notices[1].notice_doi == "10.1016/s0140-6736(10)60175-4"
    assert notices[1].record_id == "4036"


def test_crossref_expression_of_concern_then_retraction(clients: MetadataClients) -> None:
    """The Karger record has an expression of concern (2021) and a retraction (2022)."""
    notices = parse_notices(clients.crossref.work(KARGER_DOI))
    assert [n.kind for n in notices] == ["expression_of_concern", "retraction"]
    assert notices[0].is_concern
    assert notices[0].label == "Expression of concern"


def test_crossref_record_without_notices(clients: MetadataClients) -> None:
    """The PLOS paper has no notices; the trimmed record keeps only the DOI and notices."""
    record = clients.crossref.work(PLOS_DOI)
    assert record is not None
    assert set(record) == {"DOI", "updated-by"}
    assert parse_notices(record) == []


def test_crossref_skips_malformed_notices() -> None:
    """Entries without a type are ignored and bad dates become None (synthetic payload)."""
    synthetic = {
        "updated-by": [
            {"label": "no type"},
            {"type": "retraction", "updated": {"date-parts": [[2020, 13, 40]]}},
        ]
    }
    notices = parse_notices(synthetic)
    assert len(notices) == 1
    assert notices[0].notice_date is None
    assert notices[0].label == "Retraction"


def test_crossref_url_sends_no_mailto(clients: MetadataClients) -> None:
    """No personal identifier is ever added to Crossref requests."""
    assert "mailto" not in clients.crossref.url(PLOS_DOI)


def test_idconv_maps_a_doi_to_a_pmcid(clients: MetadataClients) -> None:
    """The recorded answer links the PLOS DOI to its PMC ID and PMID."""
    record = parse_record(clients.idconv.lookup(PLOS_DOI, "doi"))
    assert (record.doi, record.pmcid, record.pmid) == (PLOS_DOI, "PMC11964404", PLOS_PMID)


def test_idconv_not_in_pmc_is_none(clients: MetadataClients) -> None:
    """The recorded per-record error ("not found in PMC") means no record."""
    assert clients.idconv.lookup(LANCET_DOI, "doi") is None


@pytest.mark.parametrize(("status", "error"), [(429, UpstreamRefusedError), (503, UpstreamError)])
def test_production_fetcher_never_waits_out_retry_after(
    status: int, error: type[Exception]
) -> None:
    """A 429 or 503 with a long Retry-After fails at once: one request, no sleep."""
    requests: list[str] = []
    sleeps: list[float] = []

    def refuse(request: httpx.Request) -> httpx.Response:
        """Answer every request with the status and an hour-long Retry-After."""
        requests.append(str(request.url))
        return httpx.Response(status, headers={"Retry-After": "3600"}, content=b"{}")

    fetcher = build_metadata_fetcher(transport=httpx.MockTransport(refuse), sleep=sleeps.append)
    with pytest.raises(error):
        OpenAlexClient(fetcher).work("doi", PLOS_DOI)
    assert len(requests) == 1
    assert sleeps == []
