"""A polite, rate-limited, cached HTTP fetcher for public scholarly APIs.

Politeness rules (docs/conventions.md):

* A per-host minimum interval between requests: arXiv 3 s, NCBI E-utilities
  about 3 per second without a key, 1 s for any other host by default.
* A neutral User-Agent with no personal identifiers.
* Small, cached, resumable downloads: a response is written to a uniquely
  named temporary file and atomically renamed into the cache, so neither a
  crash nor two processes fetching the same URL can leave a truncated
  response that later runs would trust. It is served from the cache on every
  later call, so an interrupted run resumes where it stopped.
* Responses are size-limited, checked against ``Content-Length``, and
  treated as untrusted data.
* Redirects are followed by hand (at most :data:`MAX_REDIRECTS`, http(s)
  only), and every hop waits for its own host's interval.

Retries: 429 and 5xx responses are retried with exponential backoff that
honours a numeric ``Retry-After`` header (capped).

Limitation: the rate limiter is per process; concurrent processes do not
share intervals.
"""

from __future__ import annotations

import hashlib
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from urllib.parse import urljoin, urlsplit

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
MAX_REDIRECTS = 5
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_MAX_RETRY_AFTER = 60.0


class FetchError(RuntimeError):
    """Raised when a URL cannot be fetched within the rules.

    Attributes:
        status: The HTTP status of the final response when the failure was a
            non-success status (so callers can tell "not found" from "refused"
            or "unavailable"); None for every other failure.
    """

    def __init__(self, message: str, *, status: int | None = None) -> None:
        """Create the error.

        Args:
            message: What went wrong.
            status: The HTTP status, when the failure was an HTTP status.
        """
        super().__init__(message)
        self.status = status


@dataclass(frozen=True, slots=True)
class _Response:
    """The parts of one HTTP response the fetcher acts on.

    Attributes:
        status: HTTP status code.
        body: The body for success statuses, else empty.
        retry_after: Seconds from a numeric ``Retry-After`` header, if any.
        location: The ``Location`` header of a redirect, if any.
    """

    status: int
    body: bytes = b""
    retry_after: float | None = None
    location: str | None = None


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
            # Redirects are followed by hand so each hop is rate-limited.
            follow_redirects=False,
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
            FetchError: For a non-http(s) URL or redirect target, too many
                redirects, an oversized or truncated response, or a
                non-success status after retries.
        """
        _require_http(url)
        cached = self.cache_path(url) if use_cache else None
        if cached is not None and cached.is_file():
            return cached.read_bytes()

        body = self._fetch_with_retries(url)
        if cached is not None:
            _write_atomically(cached, body)
        return body

    def _fetch_with_retries(self, url: str) -> bytes:
        """Fetch a URL, following redirects and retrying 429/5xx with backoff.

        Args:
            url: An absolute http(s) URL.

        Returns:
            The final response body.

        Raises:
            FetchError: On a non-retryable status, a bad or excessive
                redirect, or when retries run out.
        """
        attempt = 0
        redirects = 0
        current = url
        while True:
            # Every request, including each redirect hop, waits for its own host.
            self._limiter.wait(urlsplit(current).netloc.lower())
            response = self._fetch_once(current)
            if response.location is not None:
                if redirects >= MAX_REDIRECTS:
                    raise FetchError(f"GET {url} exceeded {MAX_REDIRECTS} redirects")
                current = urljoin(current, response.location)
                _require_http(current)
                redirects += 1
                continue
            if response.status < 300:
                return response.body
            if response.status not in _RETRY_STATUSES or attempt >= self._max_retries:
                raise FetchError(
                    f"GET {current} returned HTTP {response.status}", status=response.status
                )
            # Back off exponentially, but defer to the server's Retry-After.
            delay = response.retry_after if response.retry_after is not None else 2.0**attempt
            self._sleep(min(delay, _MAX_RETRY_AFTER))
            attempt += 1

    def _fetch_once(self, url: str) -> _Response:
        """Perform one streamed GET without following redirects.

        Args:
            url: The URL.

        Returns:
            The status with the body (success), the ``Location`` (redirect)
            or the ``Retry-After`` delay (error).

        Raises:
            FetchError: If the body exceeds ``max_bytes``, is shorter or longer
                than its ``Content-Length``, or the request fails.
        """
        try:
            with self._client.stream("GET", url) as response:
                # A redirect without a Location is treated as an error status.
                location = response.headers.get("location")
                if response.status_code in _REDIRECT_STATUSES and location:
                    return _Response(response.status_code, location=location)
                if response.status_code >= 300:
                    return _Response(
                        response.status_code, retry_after=_retry_after(response.headers)
                    )
                # Stream with a running size check so a huge body is never held whole.
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._max_bytes:
                        raise FetchError(f"GET {url} exceeded {self._max_bytes} bytes")
                    chunks.append(chunk)
                _check_length(url, response.headers, size)
                return _Response(response.status_code, body=b"".join(chunks))
        except httpx.HTTPError as exc:
            raise FetchError(f"GET {url} failed: {exc}") from exc


def _require_http(url: str) -> None:
    """Refuse anything but an absolute http(s) URL.

    Args:
        url: The URL to check.

    Raises:
        FetchError: If the URL is not absolute http or https.
    """
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise FetchError(f"only absolute http(s) URLs may be fetched, got {url!r}")


def _check_length(url: str, headers: httpx.Headers, size: int) -> None:
    """Verify a body's size against ``Content-Length`` when it is comparable.

    The header counts encoded bytes, so it is only compared when the body was
    not content-encoded (httpx decodes gzip and similar transparently).

    Args:
        url: The URL, for the error message.
        headers: Response headers.
        size: Bytes received.

    Raises:
        FetchError: If the sizes differ (a truncated or padded response).
    """
    declared = headers.get("content-length")
    encoding = headers.get("content-encoding", "identity").strip().lower()
    if declared is None or not declared.strip().isdigit() or encoding != "identity":
        return
    if int(declared) != size:
        raise FetchError(f"GET {url} returned {size} bytes, but Content-Length is {declared}")


def _write_atomically(path: Path, body: bytes) -> None:
    """Write a cache file through a uniquely named temporary file and rename it.

    A unique name (not a fixed ``.partial``) means two processes fetching the
    same URL never write into the same temporary file; the final rename
    (``os.replace``) is atomic, so readers see either nothing or a whole body.

    Args:
        path: The cache file to create or replace.
        body: Its content.

    Raises:
        OSError: If the file cannot be written; the temporary file is removed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        # Same directory as the target, so the rename never crosses filesystems.
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(body)
        temporary.replace(path)
    except BaseException:
        # Never leave a half-written temporary file behind.
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


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
