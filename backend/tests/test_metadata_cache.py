"""The Postgres cache of metadata answers: freshness, "as of" dates, stale fallback."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from rb_backend.metadata.cache import cache_key, cached_json
from rb_backend.metadata.errors import UpstreamError
from rb_backend.metadata.models import CachedResponse, CacheSource

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)
TTL = timedelta(hours=1)


class Upstream:
    """A synthetic upstream that counts calls and can be made to fail."""

    def __init__(self, payload: Any) -> None:
        """Start answering with ``payload``."""
        self.payload = payload
        self.calls = 0
        self.fail = False

    def __call__(self) -> Any:
        """Answer, or raise if failing."""
        self.calls += 1
        if self.fail:
            raise UpstreamError("synthetic", "down", status=503)
        return self.payload


def test_first_call_fetches_and_stores_with_its_date() -> None:
    """A miss asks the service and records the answer and the time."""
    upstream = Upstream({"n": 1})
    result = cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0)
    assert (result.payload, result.as_of, result.stale) == ({"n": 1}, T0, False)
    entry = CachedResponse.objects.get()
    assert (entry.key, entry.request, entry.fetched_at) == (cache_key("123"), "123", T0)


def test_fresh_answers_are_served_without_asking() -> None:
    """Within the TTL the stored answer and its original date come back."""
    upstream = Upstream({"n": 1})
    cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0)
    result = cached_json(
        CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0 + timedelta(minutes=59)
    )
    assert upstream.calls == 1
    assert result.as_of == T0


def test_expired_answers_are_refreshed() -> None:
    """After the TTL the service is asked again and the date moves on."""
    upstream = Upstream({"n": 1})
    cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0)
    upstream.payload = {"n": 2}
    later = T0 + timedelta(hours=2)
    result = cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=later)
    assert (result.payload, result.as_of) == ({"n": 2}, later)
    assert CachedResponse.objects.count() == 1


def test_failed_refresh_serves_the_stale_answer() -> None:
    """An outage after expiry serves the old answer, marked stale, with its old date."""
    upstream = Upstream({"n": 1})
    cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0)
    upstream.fail = True
    result = cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0 + timedelta(days=1))
    assert (result.payload, result.as_of, result.stale) == ({"n": 1}, T0, True)
    assert "down" in result.error


def test_failure_with_nothing_cached_raises() -> None:
    """With no earlier answer the error reaches the caller."""
    upstream = Upstream(None)
    upstream.fail = True
    with pytest.raises(UpstreamError):
        cached_json(CacheSource.ICITE, "123", upstream, ttl=TTL, now=T0)


def test_not_found_is_cached_too() -> None:
    """A None payload ("no such record") is stored and served like any answer."""
    upstream = Upstream(None)
    cached_json(CacheSource.CROSSREF, "10.1/x", upstream, ttl=TTL, now=T0)
    result = cached_json(CacheSource.CROSSREF, "10.1/x", upstream, ttl=TTL, now=T0)
    assert result.payload is None
    assert upstream.calls == 1


def test_sources_do_not_share_keys() -> None:
    """The same request string under two sources is two entries."""
    cached_json(CacheSource.ICITE, "1", Upstream("a"), ttl=TTL, now=T0)
    result = cached_json(CacheSource.IDCONV, "1", Upstream("b"), ttl=TTL, now=T0)
    assert result.payload == "b"
    assert CachedResponse.objects.count() == 2
