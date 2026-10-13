"""A polite, rate-limited, cached HTTP fetcher for public scholarly APIs.

Politeness rules (docs/conventions.md):

* A per-host minimum interval between requests: arXiv 3 s, NCBI E-utilities
  about 3 per second without a key, 1 s for any other host by default.
* A neutral User-Agent with no personal identifiers.
* Small, cached, resumable downloads: a response is written to the cache
  atomically and served from there on every later call, so an interrupted run
  resumes where it stopped.
* Responses are size-limited and treated as untrusted data.

Retries: 429 and 5xx responses are retried with exponential backoff that
honours a numeric ``Retry-After`` header (capped).
"""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from types import TracebackType
from urllib.parse import urlsplit

import httpx

from rbcore.config import DEFAULT_USER_AGENT

# Minimum seconds between requests to the same host.
DEFAULT_HOST_INTERVALS: Mapping[str, float] = {
    "export.arxiv.org": 3.0,
    "arxiv.org": 3.0,
    "oaipmh.arxiv.org": 3.0,
    "eutils.ncbi.nlm.nih.gov": 0.34,
}
DEFAULT_INTERVAL = 1.0
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_MAX_RETRY_AFTER = 60.0


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched within the rules."""


class RateLimiter:
    """Enforces a minimum interval between calls per host."""

    def __init__(
        self,
        intervals: Mapping[str, float] | None = None,
        *,
        default_interval: float = DEFAULT_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create the limiter.

        Args:
            intervals: Per-host minimum seconds between requests.
            default_interval: Interval for hosts not in ``intervals``.
            clock: Monotonic clock (injectable for tests).
            sleep: Sleep function (injectable for tests).
        """
        self._intervals = dict(DEFAULT_HOST_INTERVALS if intervals is None else intervals)
        self._default = default_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}

    def interval_for(self, host: str) -> float:
        """Return the minimum interval for a host.

        Args:
            host: Lower-case host name.

        Returns:
            Seconds between requests.
        """
        return self._intervals.get(host, self._default)

    def wait(self, host: str) -> None:
        """Block until a request to ``host`` is allowed, then record it.

        Args:
            host: Lower-case host name.
        """
        last = self._last.get(host)
        if last is not None:
            remaining = last + self.interval_for(host) - self._clock()
            if remaining > 0:
                self._sleep(remaining)
        self._last[host] = self._clock()


class PoliteFetcher:
    """GET-only HTTP client with rate limiting, caching, retries and size limits."""

    def __init__(
        self,
        *,
        cache_dir: Path | None,
        user_agent: str = DEFAULT_USER_AGENT,
        rate_limiter: RateLimiter | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create the fetcher.

        Args:
            cache_dir: Directory for cached responses (inside the gitignored
                data/ directory), or None to disable caching.
            user_agent: User-Agent header; must not identify a person.
            rate_limiter: Rate limiter (a default one is created if None).
            transport: httpx transport (inject ``httpx.MockTransport`` in tests).
            timeout: Per-request timeout in seconds.
            max_bytes: Abort responses larger than this.
            max_retries: Retries for 429/5xx responses.
            sleep: Sleep function for backoff (injectable for tests).
        """
        self._cache_dir = cache_dir
        self._limiter = rate_limiter or RateLimiter()
        self._max_bytes = max_bytes
        self._max_retries = max_retries
        self._sleep = sleep
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=timeout,
            transport=transport,
            follow_redirects=True,
        )

    def __enter__(self) -> PoliteFetcher:
        """Enter a ``with`` block.

        Returns:
            The fetcher itself.
        """
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the underlying HTTP client on leaving a ``with`` block.

        Args:
            exc_type: Exception type, if any.
            exc: Exception, if any.
            traceback: Traceback, if any.
        """
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def cache_path(self, url: str) -> Path | None:
        """Return where a URL's response is (or would be) cached.

        Args:
            url: The URL.

        Returns:
            ``<cache_dir>/<host>/<sha256(url)>``, or None without a cache.
        """
        if self._cache_dir is None:
            return None
        host = urlsplit(url).netloc.lower() or "unknown-host"
        return self._cache_dir / host / hashlib.sha256(url.encode("utf-8")).hexdigest()

    def get(self, url: str, *, use_cache: bool = True) -> bytes:
        """Fetch a URL's body, from the cache when possible.

        Args:
            url: An http or https URL.
            use_cache: Read from and write to the cache.

        Returns:
            The response body.

        Raises:
            FetchError: For a non-http(s) URL, an oversized response, or a
                non-success status after retries.
        """
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise FetchError(f"only absolute http(s) URLs may be fetched, got {url!r}")

        cached = self.cache_path(url) if use_cache else None
        if cached is not None and cached.is_file():
            return cached.read_bytes()

        body = self._fetch_with_retries(url, parts.netloc.lower())
        if cached is not None:
            # Write to a temporary file then rename, so a crash never leaves
            # a truncated response that later runs would trust.
            cached.parent.mkdir(parents=True, exist_ok=True)
            partial = cached.with_suffix(".partial")
            partial.write_bytes(body)
            partial.replace(cached)
        return body

    def _fetch_with_retries(self, url: str, host: str) -> bytes:
        """Fetch a URL, retrying 429/5xx responses with backoff.

        Args:
            url: The URL.
            host: Its lower-case host, for rate limiting.

        Returns:
            The response body.

        Raises:
            FetchError: On a non-retryable status or when retries run out.
        """
        attempt = 0
        while True:
            self._limiter.wait(host)
            status, retry_after, body = self._fetch_once(url)
            if status < 300:
                return body
            if status not in _RETRY_STATUSES or attempt >= self._max_retries:
                raise FetchError(f"GET {url} returned HTTP {status}")
            # Back off exponentially, but defer to the server's Retry-After.
            delay = retry_after if retry_after is not None else 2.0**attempt
            self._sleep(min(delay, _MAX_RETRY_AFTER))
            attempt += 1

    def _fetch_once(self, url: str) -> tuple[int, float | None, bytes]:
        """Perform one streamed GET, enforcing the size limit.

        Args:
            url: The URL.

        Returns:
            ``(status, retry_after_seconds, body)``; the body is empty for
            error statuses.

        Raises:
            FetchError: If the body exceeds ``max_bytes`` or the request fails.
        """
        try:
            with self._client.stream("GET", url) as response:
                if response.status_code >= 300:
                    return response.status_code, _retry_after(response.headers), b""
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise FetchError(f"GET {url} exceeded {self._max_bytes} bytes")
                    chunks.append(chunk)
                return response.status_code, None, b"".join(chunks)
        except httpx.HTTPError as exc:
            raise FetchError(f"GET {url} failed: {exc}") from exc


def _retry_after(headers: httpx.Headers) -> float | None:
    """Parse a numeric ``Retry-After`` header.

    Args:
        headers: Response headers.

    Returns:
        Seconds to wait, or None if absent or not a number (HTTP dates are
        ignored in favour of exponential backoff).
    """
    value = headers.get("retry-after")
    try:
        return max(0.0, float(value)) if value is not None else None
    except ValueError:
        return None
