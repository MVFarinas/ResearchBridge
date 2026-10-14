"""Shared fixtures for the rbscores tests.

The real spaCy pipeline (``en_core_web_sm``, installed by the lock file) is
used throughout, because the features are defined on its parses. Word
familiarity comes either from the real wordfreq data or from
:class:`SyntheticFamiliarity`, a hand-written lookup that makes burden tests
independent of wordfreq's numbers.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest
from spacy.language import Language

from rbcore.http import PoliteFetcher, RateLimiter
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
def repo_root() -> Path:
    """The repository root (for committed fixtures and documented examples)."""
    return REPO_ROOT


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


# --- A synthetic Hugging Face dataset API for validation 1 tests -------------

SYNTHETIC_ABSTRACT = (
    "Pharmacological inhibition of mTORC1 attenuated phosphorylation of S6K1 in hepatocytes . "
    "Immunoblotting quantified the attenuation of downstream signalling ."
)
SYNTHETIC_LAY = (
    "The drug blocked a growth signal in liver cells . We checked this with a simple lab test ."
)
SYNTHETIC_BODY_SENTENCE = (
    "The synthetic cells were measured carefully in this made-up test sentence for calibration ."
)


def _synthetic_rows(split: str) -> list[dict[str, Any]]:
    """Build SYNTHETIC dataset rows (not real data) for one split."""
    body = " ".join([SYNTHETIC_BODY_SENTENCE] * 15)
    good = {
        "article": f"{SYNTHETIC_ABSTRACT}\n{body}\n{body}",
        "summary": f"{SYNTHETIC_LAY}\n{SYNTHETIC_LAY}",
        "section_headings": ["Abstract", "Introduction", "Results"],
        "keywords": ["synthetic"],
        "year": "2020",
        "title": "Synthetic paper",
    }
    no_abstract = good | {"section_headings": ["Introduction", "Results"]}
    rows = [
        {"row_idx": 0, "row": good, "truncated_cells": []},
        {"row_idx": 1, "row": no_abstract, "truncated_cells": []},
        {"row_idx": 2, "row": good, "truncated_cells": ["article"]},
        {"row_idx": 3, "row": good | {"title": "Synthetic paper 2"}, "truncated_cells": []},
    ]
    return rows if split == "validation" else rows[:1] + rows[2:]


def synthetic_hub_handler(request: httpx.Request) -> httpx.Response:
    """Answer rows-API and dataset-info requests with SYNTHETIC data."""
    if request.url.host == "huggingface.co":
        return httpx.Response(200, json={"sha": "synthetic-sha"})
    params = request.url.params
    rows = _synthetic_rows(params["split"])
    offset, length = int(params["offset"]), int(params["length"])
    page = {
        "features": [],
        "rows": rows[offset : offset + length],
        "num_rows_total": len(rows),
        "num_rows_per_page": 100,
        "partial": False,
    }
    return httpx.Response(200, json=page)


@pytest.fixture
def synthetic_hub(tmp_path: Path) -> Iterator[PoliteFetcher]:
    """A PoliteFetcher wired to the synthetic hub, with no real sleeping."""
    limiter = RateLimiter(default_interval=0.0, sleep=lambda _: None)
    fetcher = PoliteFetcher(
        cache_dir=tmp_path / "cache",
        transport=httpx.MockTransport(synthetic_hub_handler),
        rate_limiter=limiter,
        sleep=lambda _: None,
    )
    with fetcher:
        yield fetcher
