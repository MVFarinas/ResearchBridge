"""Shared pytest fixtures for rbcore tests."""

from __future__ import annotations

from collections.abc import Callable
from functools import cache
from pathlib import Path

import pytest

from rbcore.jats import Article, parse_jats_file

FIXTURES = Path(__file__).parent / "fixtures" / "jats"


@cache
def _load(name: str) -> Article:
    """Parse a fixture once per test session.

    Args:
        name: File name inside tests/fixtures/jats.

    Returns:
        The parsed article.
    """
    return parse_jats_file(FIXTURES / name)


@pytest.fixture
def fixture_dir() -> Path:
    """Directory holding the real JATS fixtures."""
    return FIXTURES


@pytest.fixture
def load_article() -> Callable[[str], Article]:
    """Return a loader that parses (and caches) a real JATS fixture by file name."""
    return _load
