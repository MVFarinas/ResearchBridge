"""The throttle store keeps rate-limit histories under load."""

from __future__ import annotations

from typing import Any, cast

import pytest
from django.conf import settings
from django.core.cache import cache

pytestmark = pytest.mark.django_db

# Comfortably more than Django's default MAX_ENTRIES (300).
MANY_CLIENTS = 400


def test_cache_is_sized_far_beyond_djangos_default() -> None:
    """The cache's entry limit is configured, not Django's default of 300."""
    options = cast(dict[str, Any], settings.CACHES["default"]["OPTIONS"])
    assert options["MAX_ENTRIES"] == settings.RB_CACHE_MAX_ENTRIES >= 100_000


def test_throttle_histories_survive_hundreds_of_clients() -> None:
    """Hundreds of live throttle keys are all kept (the default would cull a third)."""
    # Shaped like DRF's scoped throttle keys: one per scope and (synthetic) address.
    keys = [f"throttle_search_192.0.2.{i % 250}-{i}" for i in range(MANY_CLIENTS)]
    for key in keys:
        cache.set(key, [1.0], timeout=60)
    assert all(cache.get(key) == [1.0] for key in keys)
