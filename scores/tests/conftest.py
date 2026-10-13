"""Shared fixtures for the rbscores tests.

The real spaCy pipeline (``en_core_web_sm``, installed by the lock file) is
used throughout, because the features are defined on its parses. Word
familiarity comes either from the real wordfreq data or from
:class:`SyntheticFamiliarity`, a hand-written lookup that makes burden tests
independent of wordfreq's numbers.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest
from spacy.language import Language

from rbscores.familiarity import WordfreqFamiliarity
from rbscores.nlp import load_pipeline
from rbscores.readability.composite import ReferenceStats, reference_from_json
from rbscores.readability.features import FEATURE_NAMES

REPO_ROOT = Path(__file__).resolve().parents[2]
JATS_FIXTURES = REPO_ROOT / "libs" / "rbcore" / "tests" / "fixtures" / "jats"


class SyntheticFamiliarity:
    """A synthetic word-frequency lookup: listed words get their Zipf value, others are common."""

    def __init__(self, zipfs: Mapping[str, float], default: float = 6.0) -> None:
        """Create the lookup.

        Args:
            zipfs: Lower-case word to Zipf value.
            default: Zipf value of every unlisted word (common by default).
        """
        self._zipfs = {k.lower(): v for k, v in zipfs.items()}
        self._default = default

    def zipf(self, word: str) -> float:
        """Return the listed Zipf value, or the default.

        Args:
            word: A word.

        Returns:
            Its synthetic Zipf value.
        """
        return self._zipfs.get(word.lower(), self._default)


@pytest.fixture(scope="session")
def jats_fixtures() -> Path:
    """Directory of the real CC BY JATS fixtures committed with rbcore."""
    return JATS_FIXTURES


@pytest.fixture
def make_familiarity() -> type[SyntheticFamiliarity]:
    """The :class:`SyntheticFamiliarity` class, for tests to instantiate."""
    return SyntheticFamiliarity


@pytest.fixture(scope="session")
def nlp() -> Language:
    """The real spaCy pipeline, loaded once."""
    return load_pipeline()


@pytest.fixture(scope="session")
def wordfreq_familiarity() -> WordfreqFamiliarity:
    """The real wordfreq-backed familiarity lookup."""
    return WordfreqFamiliarity()


@pytest.fixture
def synthetic_reference() -> ReferenceStats:
    """Synthetic reference statistics: mean 0 and SD 1 for every feature."""
    return reference_from_json(
        {
            "version": "synthetic-test-reference",
            "description": "SYNTHETIC: identity z-scores for tests",
            "units": 2,
            "features": {name: {"mean": 0.0, "sd": 1.0} for name in FEATURE_NAMES},
        }
    )
