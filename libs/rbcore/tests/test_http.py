"""Tests for rbcore.http, using httpx.MockTransport (no network)."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from rbcore.config import DEFAULT_USER_AGENT
from rbcore.http import FetchError, PoliteFetcher, RateLimiter


class FakeClock:
    """Manually advanced clock whose sleep() advances time and is recorded."""

    def __init__(self) -> None:
        """Start at t=100."""
        self.now = 100.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        """Return the current time."""
        return self.now

    def sleep(self, seconds: float) -> None:
        """Record a sleep and advance time."""
        self.sleeps.append(seconds)
        self.now += seconds


def _fetcher(
    handler: httpx.MockTransport,
    tmp_path: Path | None,
    clock: FakeClock,
    *,
    max_bytes: int = 1024 * 1024,
    max_retries: int = 3,
) -> PoliteFetcher:
    """Build a fetcher on a mock transport with a fake clock."""
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    return PoliteFetcher(
        cache_dir=tmp_path,
        rate_limiter=limiter,
        transport=handler,
        sleep=clock.sleep,
        max_bytes=max_bytes,
        max_retries=max_retries,
    )


def test_rate_limiter_spaces_requests_per_host() -> None:
    """The arXiv host gets 3 s between requests; hosts are limited independently."""
    clock = FakeClock()
    limiter = RateLimiter(clock=clock, sleep=clock.sleep)
    limiter.wait("export.arxiv.org")
    limiter.wait("www.ebi.ac.uk")  # a different host does not wait
    clock.now += 1.0
    limiter.wait("export.arxiv.org")
    assert clock.sleeps == [pytest.approx(2.0)]
    assert limiter.interval_for("eutils.ncbi.nlm.nih.gov") == pytest.approx(0.34)
    assert limiter.interval_for("unknown.example") == 1.0


def test_get_sends_user_agent_and_caches(tmp_path: Path) -> None:
    """The neutral User-Agent is sent; a second get is served from the cache."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Return a fixed body and record the request."""
        seen.append(request)
        return httpx.Response(200, content=b"<article/>")

    clock = FakeClock()
    with _fetcher(httpx.MockTransport(handler), tmp_path, clock) as fetcher:
        url = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1/fullTextXML"
        assert fetcher.get(url) == b"<article/>"
        assert fetcher.get(url) == b"<article/>"
        cached = fetcher.cache_path(url)
    assert len(seen) == 1
    assert seen[0].headers["User-Agent"] == DEFAULT_USER_AGENT
    assert cached is not None
    assert cached.read_bytes() == b"<article/>"
    assert cached.parent.name == "www.ebi.ac.uk"
    assert not list(tmp_path.rglob("*.partial"))


def test_use_cache_false_refetches(tmp_path: Path) -> None:
    """use_cache=False bypasses the cache."""
    count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        """Count calls."""
        nonlocal count
        count += 1
        return httpx.Response(200, content=b"x")

    with _fetcher(httpx.MockTransport(handler), tmp_path, FakeClock()) as fetcher:
        fetcher.get("https://example.org/a", use_cache=False)
        fetcher.get("https://example.org/a", use_cache=False)
    assert count == 2


def test_retries_429_honouring_retry_after() -> None:
    """429 then 200: one retry, waiting the server's Retry-After."""
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, content=b"ok")]
    )
    clock = FakeClock()
    with _fetcher(httpx.MockTransport(lambda r: next(responses)), None, clock) as fetcher:
        assert fetcher.get("https://example.org/x") == b"ok"
    assert 7.0 in clock.sleeps


def test_gives_up_after_max_retries() -> None:
    """Persistent 503s raise FetchError after the configured retries, backing off."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        """Always fail."""
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    clock = FakeClock()
    with (
        _fetcher(httpx.MockTransport(handler), None, clock, max_retries=2) as fetcher,
        pytest.raises(FetchError, match="503"),
    ):
        fetcher.get("https://example.org/x")
    assert calls == 3
    assert 1.0 in clock.sleeps
    assert 2.0 in clock.sleeps


def test_client_errors_are_not_retried() -> None:
    """A 404 fails immediately."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        """Always 404."""
        nonlocal calls
        calls += 1
        return httpx.Response(404)

    with (
        _fetcher(httpx.MockTransport(handler), None, FakeClock()) as fetcher,
        pytest.raises(FetchError, match="404"),
    ):
        fetcher.get("https://example.org/missing")
    assert calls == 1


def test_size_limit_aborts_large_responses(tmp_path: Path) -> None:
    """Responses over max_bytes raise and are not cached."""
    handler = httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 1000))
    with (
        _fetcher(handler, tmp_path, FakeClock(), max_bytes=100) as fetcher,
        pytest.raises(FetchError, match="exceeded"),
    ):
        fetcher.get("https://example.org/big")
    assert not any(p.is_file() for p in tmp_path.rglob("*"))


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/x", "/relative/path"])
def test_only_http_urls_are_allowed(url: str) -> None:
    """Non-http(s) URLs are refused before any request."""
    handler = httpx.MockTransport(lambda r: httpx.Response(200))
    with _fetcher(handler, None, FakeClock()) as fetcher, pytest.raises(FetchError, match="http"):
        fetcher.get(url)


def test_transport_errors_become_fetch_errors() -> None:
    """Connection failures are reported as FetchError."""

    def handler(request: httpx.Request) -> httpx.Response:
        """Simulate a connection failure."""
        raise httpx.ConnectError("refused", request=request)

    with (
        _fetcher(httpx.MockTransport(handler), None, FakeClock()) as fetcher,
        pytest.raises(FetchError, match="refused"),
    ):
        fetcher.get("https://example.org/x")
