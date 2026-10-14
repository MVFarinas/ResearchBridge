"""Process-wide clients for ingestion: one polite fetcher, one bucket client.

Rate limits in :class:`rbcore.http.PoliteFetcher` are per instance, so a
process must share one fetcher for the limits to hold. Procrastinate runs
synchronous tasks in worker threads, so the shared clients are created once
under a lock, and :data:`INGEST_LOCK` serialises ingestion in a process: at
most one article is fetched at a time, whatever the worker's concurrency.

The lookup API checks the bucket from inside a web request, where waiting out
a ``Retry-After`` or a 30 s timeout would outlast the web server's worker
timeout; :func:`get_request_bucket` gives it a separate fetcher with a short
timeout and no retries.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from functools import cache
from urllib.parse import urlsplit

import httpx
from django.conf import settings

from rb_backend.ingestion.pmc import BASE_URL, PmcBucket
from rbcore.config import Settings
from rbcore.http import DEFAULT_HOST_INTERVALS, PoliteFetcher, RateLimiter

# The bucket is S3 and could take far more, but small and steady is polite.
BUCKET_INTERVAL_SECONDS = 0.5
# Bucket checks made inside a web request: fail fast rather than wait.
REQUEST_TIMEOUT_SECONDS = 5.0
REQUEST_MAX_RETRIES = 0

INGEST_LOCK = threading.Lock()
_CREATE_LOCK = threading.Lock()


def host_intervals() -> dict[str, float]:
    """Per-host minimum intervals: rbcore's defaults plus the PMC bucket.

    Returns:
        Seconds between requests, by host.
    """
    return {**DEFAULT_HOST_INTERVALS, urlsplit(BASE_URL).netloc: BUCKET_INTERVAL_SECONDS}


@cache
def _fetcher() -> PoliteFetcher:
    """Create the process's fetcher (cache under ``RB_DATA_DIR/http-cache``).

    Returns:
        The fetcher.
    """
    rb_settings = Settings.from_env()
    return PoliteFetcher(
        cache_dir=settings.RB_DATA_DIR / "http-cache",
        user_agent=rb_settings.user_agent,
        rate_limiter=RateLimiter(host_intervals()),
    )


def get_fetcher() -> PoliteFetcher:
    """Return the process-wide polite fetcher.

    Returns:
        The shared fetcher.
    """
    with _CREATE_LOCK:
        return _fetcher()


def get_bucket() -> PmcBucket:
    """Return a bucket client on the shared fetcher.

    Returns:
        The client.
    """
    return PmcBucket(get_fetcher())


def build_request_fetcher(
    *,
    transport: httpx.BaseTransport | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> PoliteFetcher:
    """Build a fetcher for bucket checks made inside a web request.

    It has no disk cache (the lookup reads listings and metadata uncached
    anyway), a short timeout and no retries, so a refusal or outage is
    reported to the reader at once.

    Args:
        transport: An httpx transport (tests pass ``httpx.MockTransport``).
        sleep: The sleep used by the rate limiter and for retry back-off
            (injectable so tests can prove no back-off happens).

    Returns:
        The fetcher.
    """
    return PoliteFetcher(
        cache_dir=None,
        user_agent=Settings.from_env().user_agent,
        rate_limiter=RateLimiter(host_intervals(), sleep=sleep),
        transport=transport,
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_retries=REQUEST_MAX_RETRIES,
        sleep=sleep,
    )


@cache
def _request_fetcher() -> PoliteFetcher:
    """Create the process's fetcher for in-request bucket checks.

    Returns:
        The fetcher from :func:`build_request_fetcher`.
    """
    return build_request_fetcher()


def get_request_bucket() -> PmcBucket:
    """Return a bucket client for use inside a web request (lookup).

    Returns:
        A client whose fetcher never retries and times out quickly.
    """
    with _CREATE_LOCK:
        return PmcBucket(_request_fetcher())


def ncbi_api_key() -> str | None:
    """The optional NCBI API key from the environment.

    Returns:
        The key, or None (E-utilities then allows about 3 requests per second).
    """
    return Settings.from_env().ncbi_api_key
