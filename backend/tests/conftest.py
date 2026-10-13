"""Shared pytest fixtures; the builders they wrap live in ``support.py``."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from support import RecordedBucket

from rb_backend.ingestion.pmc import PmcBucket
from rbcore.http import PoliteFetcher, RateLimiter


@pytest.fixture
def recorded() -> RecordedBucket:
    """The fake bucket host, with no synthetic overrides yet."""
    return RecordedBucket()


@pytest.fixture
def fetcher(recorded: RecordedBucket, tmp_path: Path) -> Iterator[PoliteFetcher]:
    """A polite fetcher on the fake host, with no rate-limit delays and a temp cache."""
    with PoliteFetcher(
        cache_dir=tmp_path / "http-cache",
        transport=httpx.MockTransport(recorded.handler),
        rate_limiter=RateLimiter({}, default_interval=0.0),
        sleep=lambda _: None,
    ) as polite:
        yield polite


@pytest.fixture
def bucket(fetcher: PoliteFetcher) -> PmcBucket:
    """A bucket client on the fake host."""
    return PmcBucket(fetcher)
