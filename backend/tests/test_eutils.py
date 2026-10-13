"""ESearch discovery: query building, parsing and paging (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from support import PMC_FIXTURES

from rb_backend.ingestion.eutils import (
    IN_BUCKET_FILTER,
    EsearchError,
    build_term,
    esearch_url,
    parse_esearch,
    search_pmc,
)
from rbcore.http import PoliteFetcher, RateLimiter


def test_build_term_adds_bucket_and_licence_filters() -> None:
    """User queries are wrapped and combined with the README's in-bucket filter."""
    term = build_term("asthma OR copd", licence="cc-by")
    assert term == f"(asthma OR copd) AND {IN_BUCKET_FILTER} AND cc_by_license[Filter]"
    assert build_term("") == IN_BUCKET_FILTER


def test_build_term_rejects_unknown_licence_filter() -> None:
    """A typo in the licence filter is an error, not an unfiltered search."""
    with pytest.raises(ValueError, match="unknown licence filter"):
        build_term("x", licence="cc-by-everything")


def test_esearch_url_sends_no_personal_identifier() -> None:
    """The URL names the tool, never an email; the key is optional."""
    params = parse_qs(urlsplit(esearch_url("x", retmax=5)).query)
    assert params["tool"] == ["researchbridge"]
    assert "email" not in params
    assert "api_key" not in params
    keyed = parse_qs(urlsplit(esearch_url("x", retmax=5, api_key="synthetic-key")).query)
    assert keyed["api_key"] == ["synthetic-key"]


def test_parse_recorded_response() -> None:
    """The recorded response yields a count and PMC-prefixed IDs."""
    result = parse_esearch((PMC_FIXTURES / "esearch-hypertension-2024-cc-by.json").read_bytes())
    assert result.count == 76568
    assert result.pmcids == (
        "PMC13649809",
        "PMC13646441",
        "PMC13649112",
        "PMC13649093",
        "PMC13648882",
    )


@pytest.mark.parametrize(
    "document",
    [
        b"<html>",
        b'{"esearchresult": {"ERROR": "bad query"}}',
        b'{"esearchresult": {"count": "1", "idlist": ["x"]}}',
    ],
)
def test_parse_refuses_errors_and_garbage(document: bytes) -> None:
    """Errors and non-numeric IDs raise instead of producing bogus PMC IDs."""
    with pytest.raises(EsearchError):
        parse_esearch(document)


def test_search_pages_until_limit(tmp_path: Path) -> None:
    """Paging continues with retstart and stops at the limit (synthetic pages)."""
    seen: list[dict[str, list[str]]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Serve two synthetic pages of three IDs each."""
        params = parse_qs(request.url.query.decode())
        seen.append(params)
        start = int(params["retstart"][0])
        ids = [str(1000 + start + i) for i in range(int(params["retmax"][0]))][:3]
        body = {"esearchresult": {"count": "6", "retstart": str(start), "idlist": ids}}
        return httpx.Response(200, json=body)

    with PoliteFetcher(
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
        rate_limiter=RateLimiter({}, default_interval=0.0),
    ) as fetcher:
        found = search_pmc(fetcher, "synthetic", limit=5)
    assert found == ["PMC1000", "PMC1001", "PMC1002", "PMC1003", "PMC1004"]
    assert [p["retstart"] for p in seen] == [["0"], ["3"]]
    assert not list(tmp_path.rglob("*")), "search results are never cached"


def test_search_stops_when_results_run_out(tmp_path: Path) -> None:
    """A short result set ends the paging loop."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Serve one synthetic page with two IDs."""
        return httpx.Response(
            200, content=json.dumps({"esearchresult": {"count": "2", "idlist": ["1", "2"]}})
        )

    with PoliteFetcher(
        cache_dir=None,
        transport=httpx.MockTransport(handler),
        rate_limiter=RateLimiter({}, default_interval=0.0),
    ) as fetcher:
        assert search_pmc(fetcher, "synthetic", limit=50) == ["PMC1", "PMC2"]
