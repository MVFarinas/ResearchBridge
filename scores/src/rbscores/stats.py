"""Small, dependency-free statistics used by the validations.

Implemented here rather than pulling in SciPy for five functions; each is
tested against hand-computed or published values.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

Z_95 = 1.959963984540054
"""Two-sided 95% standard-normal quantile."""


@dataclass(frozen=True, slots=True)
class Proportion:
    """A binomial proportion with its Wilson score interval.

    Attributes:
        successes: Number of successes.
        n: Number of trials.
        low: Lower bound of the interval.
        high: Upper bound of the interval.
    """

    successes: int
    n: int
    low: float
    high: float

    @property
    def value(self) -> float:
        """The observed proportion (0 when there are no trials)."""
        return self.successes / self.n if self.n else 0.0


def wilson_interval(successes: int, n: int, *, z: float = Z_95) -> Proportion:
    """Compute a Wilson score interval for a binomial proportion.

    Args:
        successes: Number of successes, 0 to ``n``.
        n: Number of trials.
        z: Normal quantile (default: 95% two-sided).

    Returns:
        The proportion and interval; (0, 1) when ``n`` is 0.

    Raises:
        ValueError: If ``successes`` is outside 0 to ``n``.
    """
    if not 0 <= successes <= n:
        raise ValueError(f"successes must be between 0 and n, got {successes} of {n}")
    if n == 0:
        return Proportion(0, 0, 0.0, 1.0)
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return Proportion(successes, n, max(0.0, centre - half), min(1.0, centre + half))


def sign_test_p(successes: int, n: int) -> float:
    """Two-sided exact binomial (sign) test of a proportion against 0.5.

    Args:
        successes: Number of successes.
        n: Number of trials (ties already excluded).

    Returns:
        The two-sided p-value (1.0 when ``n`` is 0).
    """
    if n == 0:
        return 1.0
    extreme = min(successes, n - successes)
    tail = sum(math.comb(n, k) for k in range(extreme + 1))
    # Exact integer ratio: int / int division stays accurate for large n.
    return min(1.0, 2 * tail / (1 << n))


def average_ranks(values: Sequence[float]) -> list[float]:
    """Rank values from 1, giving tied values their average rank.

    Args:
        values: Values to rank.

    Returns:
        Ranks aligned with ``values``.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        # Find the run of equal values and give each the run's mean rank.
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        mean_rank = (start + end) / 2 + 1
        for position in range(start, end + 1):
            ranks[order[position]] = mean_rank
        start = end + 1
    return ranks


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Pearson correlation.

    Args:
        xs: First variable.
        ys: Second variable, same length.

    Returns:
        The correlation, or None if fewer than two pairs or a variable is constant.

    Raises:
        ValueError: If the lengths differ.
    """
    if len(xs) != len(ys):
        raise ValueError("xs and ys must have the same length")
    # A correlation needs at least two points.
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mean_x) ** 2 for x in xs)
    syy = sum((y - mean_y) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank correlation (Pearson on average ranks, so ties are handled).

    Args:
        xs: First variable.
        ys: Second variable, same length.

    Returns:
        The correlation, or None if it is undefined.
    """
    return pearson(average_ranks(xs), average_ranks(ys))


def auc(positives: Sequence[float], negatives: Sequence[float]) -> float | None:
    """Area under the ROC curve: P(score of a positive > score of a negative).

    Ties count one half (the Mann-Whitney statistic divided by n1 x n2).

    Args:
        positives: Scores of positive items.
        negatives: Scores of negative items.

    Returns:
        The AUC, or None if either group is empty.
    """
    if not positives or not negatives:
        return None
    ranks = average_ranks([*positives, *negatives])
    n_pos, n_neg = len(positives), len(negatives)
    rank_sum = sum(ranks[:n_pos])
    return (rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def median(values: Sequence[float]) -> float | None:
    """Median of a sequence.

    Args:
        values: Values.

    Returns:
        The median, or None if empty.
    """
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2
