"""Process-wide clients for ingestion: one polite fetcher, one bucket client.

Rate limits in :class:`rbcore.http.PoliteFetcher` are per instance, so a
process must share one fetcher for the limits to hold. Procrastinate runs
synchronous tasks in worker threads, so the shared clients are created once
under a lock, and :data:`INGEST_LOCK` serialises ingestion in a process: at
most one article is fetched at a time, whatever the worker's concurrency.
"""

from __future__ import annotations

import threading
from functools import cache
from urllib.parse import urlsplit

from django.conf import settings

from rb_backend.ingestion.pmc import BASE_URL, PmcBucket
from rbcore.config import Settings
from rbcore.http import DEFAULT_HOST_INTERVALS, PoliteFetcher, RateLimiter

# The bucket is S3 and could take far more, but small and steady is polite.
BUCKET_INTERVAL_SECONDS = 0.5

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


def ncbi_api_key() -> str | None:
    """The optional NCBI API key from the environment.

    Returns:
        The key, or None (E-utilities then allows about 3 requests per second).
    """
    return Settings.from_env().ncbi_api_key
