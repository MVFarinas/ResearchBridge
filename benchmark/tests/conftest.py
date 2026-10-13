"""Shared pytest fixtures for rbbench tests.

Ratings built here are SYNTHETIC test data, never real ratings.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

import pytest

from rbbench.ratings import Rating
from rbbench.rubric import Rubric, Unit, load_rubric

# Labels for every claim-level code of rubric_v1, all "clean".
CLEAN_CLAIM_LABELS: Mapping[str, str] = {
    "support": "supported",
    "overgen_generic": "no",
    "overgen_present_tense": "no",
    "overgen_action_guiding": "no",
    "lost_hedge": "no",
    "correlation_to_causation": "no",
    "spin": "no",
    "substituted_detail": "no",
    "added_information": "no",
}


@pytest.fixture
def clean_claim_labels() -> dict[str, str]:
    """A fresh copy of all-clean labels for every claim-level code of rubric_v1."""
    return dict(CLEAN_CLAIM_LABELS)


@pytest.fixture(scope="session")
def rubric() -> Rubric:
    """The committed rubric_v1."""
    return load_rubric()


@pytest.fixture
def make_synthetic_rating(rubric: Rubric) -> Callable[..., Rating]:
    """Return a factory for SYNTHETIC claim ratings that start from clean labels."""

    def factory(rater_id: str, unit_id: str, **overrides: str) -> Rating:
        """Build one synthetic claim rating with selected labels overridden."""
        labels = {**CLEAN_CLAIM_LABELS, **overrides}
        return Rating(
            rater_id=rater_id,
            unit=Unit.CLAIM,
            unit_id=unit_id,
            labels=labels,
            rubric_id=rubric.id,
            rubric_sha256=rubric.sha256,
            synthetic=True,
        )

    return factory
