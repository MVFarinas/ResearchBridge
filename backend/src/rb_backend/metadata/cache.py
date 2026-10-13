"""A Postgres cache for metadata responses, with "as of" dates and stale fallback.

:func:`cached_json` serves a fresh cached answer, otherwise asks the service.
If the service fails and an older answer exists, the older answer is served
and marked stale (with its original "as of" date), so the reader keeps
showing what was known and says when it was known. "Not found" answers are
cached like any other.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from django.utils import timezone

from rb_backend.metadata.errors import UpstreamError
from rb_backend.metadata.models import CachedResponse, CacheSource


@dataclass(frozen=True, slots=True)
class CacheResult:
    """A metadata answer and how current it is.

    Attributes:
        payload: The trimmed JSON answer, or None when the service had no
            such record.
        as_of: When the service gave this answer.
        stale: True when a refresh failed and an older answer is served.
        error: Why the refresh failed ("" otherwise).
    """

    payload: Any
    as_of: datetime
    stale: bool = False
    error: str = ""


def cache_key(request: str) -> str:
    """The cache key of a canonical request string.

    Args:
        request: The canonical request (never containing secrets).

    Returns:
        Its SHA-256 hex digest.
    """
    return hashlib.sha256(request.encode("utf-8")).hexdigest()


def cached_json(
    source: CacheSource,
    request: str,
    fetch: Callable[[], Any],
    *,
    ttl: timedelta,
    now: datetime | None = None,
) -> CacheResult:
    """Return a cached answer, refreshing it when older than ``ttl``.

    Args:
        source: The kind of request.
        request: The canonical request string (no secrets).
        fetch: Asks the service; returns the trimmed JSON payload, or None
            for "not found". Raises :class:`UpstreamError` on failure.
        ttl: How long an answer stays fresh.
        now: Current time (default: now).

    Returns:
        The answer.

    Raises:
        UpstreamError: If the service fails and nothing was cached before.
    """
    now = now or timezone.now()
    key = cache_key(request)
    entry = CachedResponse.objects.filter(source=source, key=key).first()

    # A fresh entry is served without asking the service.
    if entry is not None and entry.fetched_at + ttl > now:
        return CacheResult(entry.payload, entry.fetched_at)

    # Otherwise refresh; on failure fall back to the stale entry if there is one.
    try:
        payload = fetch()
    except UpstreamError as exc:
        if entry is None:
            raise
        return CacheResult(entry.payload, entry.fetched_at, stale=True, error=str(exc))

    CachedResponse.objects.update_or_create(
        source=source,
        key=key,
        defaults={"request": request, "payload": payload, "fetched_at": now},
    )
    return CacheResult(payload, now)
