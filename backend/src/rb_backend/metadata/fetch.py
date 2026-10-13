"""JSON over the polite fetcher, with errors mapped and secrets redacted.

The metadata clients share one :class:`rbcore.http.PoliteFetcher` per
process (rate limits are per fetcher instance). Calls are made from request
handlers, so the fetcher has a short timeout and a single retry; a lock
serialises calls so the per-host intervals hold across request threads.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Sequence
from functools import cache
from typing import Any

from rb_backend.metadata.errors import UpstreamError, UpstreamRefusedError
from rbcore.config import Settings
from rbcore.http import DEFAULT_HOST_INTERVALS, FetchError, PoliteFetcher, RateLimiter

# Statuses that mean "refused" rather than "broken": no key, budget spent, rate limited.
REFUSED_STATUSES = frozenset({401, 402, 403, 429})
# Minimum seconds between requests per host (OpenAlex allows 10/s keyless; NCBI 3/s).
METADATA_HOST_INTERVALS: dict[str, float] = {
    **DEFAULT_HOST_INTERVALS,
    "api.openalex.org": 0.5,
    "api.crossref.org": 1.0,
    "icite.od.nih.gov": 1.0,
    "pmc.ncbi.nlm.nih.gov": 0.34,
}
REQUEST_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
REDACTED = "[redacted]"

_LOCK = threading.Lock()


def redact(text: str, secrets: Sequence[str | None]) -> str:
    """Remove secret values from a message.

    Args:
        text: The message.
        secrets: Values to hide (None and "" are ignored).

    Returns:
        The message with every secret replaced by ``[redacted]``.
    """
    for secret in secrets:
        if secret:
            text = text.replace(secret, REDACTED)
    return text


def get_json(
    fetcher: PoliteFetcher, url: str, *, source: str, secrets: Sequence[str | None] = ()
) -> Any:
    """GET a URL and decode its JSON body.

    Args:
        fetcher: The polite fetcher.
        url: The URL (may contain a secret, such as an API key parameter).
        source: The service name, for errors.
        secrets: Values to redact from any error message.

    Returns:
        The decoded JSON, or None when the service answered 404.

    Raises:
        UpstreamRefusedError: For 401, 402, 403 and 429.
        UpstreamError: For any other failure, including invalid JSON.
    """
    # Fetch without the on-disk cache: answers are cached, with dates, in Postgres.
    try:
        with _LOCK:
            body = fetcher.get(url, use_cache=False)
    except FetchError as exc:
        if exc.status == 404:
            return None
        message = redact(str(exc), secrets)
        if exc.status in REFUSED_STATUSES:
            raise UpstreamRefusedError(source, message, status=exc.status) from None
        raise UpstreamError(source, message, status=exc.status) from None

    # The body is untrusted data: decode it and nothing more.
    try:
        return json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise UpstreamError(source, "the response was not valid JSON") from None


@cache
def _fetcher() -> PoliteFetcher:
    """Create the process's metadata fetcher.

    Returns:
        A fetcher with no disk cache, a short timeout and one retry.
    """
    return PoliteFetcher(
        cache_dir=None,
        user_agent=Settings.from_env().user_agent,
        rate_limiter=RateLimiter(METADATA_HOST_INTERVALS),
        timeout=REQUEST_TIMEOUT_SECONDS,
        max_bytes=MAX_RESPONSE_BYTES,
        max_retries=1,
    )


def metadata_fetcher() -> PoliteFetcher:
    """Return the process-wide metadata fetcher.

    Returns:
        The shared fetcher.
    """
    with _LOCK:
        return _fetcher()
