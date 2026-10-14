"""Tests for the statistics helpers, against hand-computed and published values."""

from __future__ import annotations

import pytest

from rbscores.stats import (
    auc,
    average_ranks,
    median,
    pearson,
    sign_test_p,
    spearman,
    wilson_interval,
)


def test_wilson_interval_matches_published_example() -> None:
    """Newcombe (1998) example: 81/263 gives about 0.2553 to 0.3662."""
    result = wilson_interval(81, 263)
    assert result.value == pytest.approx(81 / 263)
    assert result.low == pytest.approx(0.2553, abs=5e-4)
    assert result.high == pytest.approx(0.3662, abs=5e-4)


def test_wilson_interval_edges() -> None:
    """All successes stays inside [0, 1]; no trials gives the whole range."""
    full = wilson_interval(10, 10)
    assert full.high == pytest.approx(1.0)
    assert 0.65 < full.low < 0.75
    empty = wilson_interval(0, 0)
    assert (empty.value, empty.low, empty.high) == (0.0, 0.0, 1.0)
    with pytest.raises(ValueError, match="between 0 and n"):
        wilson_interval(5, 3)


def test_sign_test() -> None:
    """Exact binomial two-sided p-values."""
    assert sign_test_p(5, 10) == 1.0
    assert sign_test_p(10, 10) == pytest.approx(2 / 1024)
    assert sign_test_p(0, 10) == pytest.approx(2 / 1024)
    assert sign_test_p(8, 10) == pytest.approx(2 * (1 + 10 + 45) / 1024)
    assert sign_test_p(0, 0) == 1.0
    # Large n (validation 1 has 1,617 pairs) must not overflow.
    assert sign_test_p(1300, 1617) < 1e-100
    assert sign_test_p(800, 1600) > 0.5


def test_average_ranks_handle_ties() -> None:
    """Tied values share the mean of their ranks."""
    assert average_ranks([10, 20, 20, 30]) == [1.0, 2.5, 2.5, 4.0]
    assert average_ranks([3, 1, 2]) == [3.0, 1.0, 2.0]


def test_correlations() -> None:
    """Pearson and Spearman on simple data; undefined cases give None."""
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [1, 4, 9, 16]) == pytest.approx(1.0)
    assert spearman([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert pearson([1], [1]) is None
    with pytest.raises(ValueError, match="same length"):
        pearson([1, 2], [1])


def test_auc() -> None:
    """AUC is the share of positive-negative pairs ordered correctly (ties half)."""
    assert auc([3, 4], [1, 2]) == 1.0
    assert auc([1, 2], [3, 4]) == 0.0
    assert auc([1, 3], [2, 2]) == pytest.approx(0.5)
    assert auc([], [1]) is None


def test_median() -> None:
    """Odd and even lengths, and empty input."""
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 2, 3]) == 2.5
    assert median([]) is None
