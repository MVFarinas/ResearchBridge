"""Agreement and correlation statistics, implemented from their definitions.

* Cohen's kappa for two raters (Cohen 1960).
* Fleiss' kappa for a fixed number of raters per subject (Fleiss 1971).
* Krippendorff's alpha for nominal data, with missing values (Krippendorff
  2011, "Computing Krippendorff's Alpha-Reliability").
* Kendall's tau-b, the tie-corrected rank correlation FactPICO reports.

Pure Python on purpose: the PyPI ``krippendorff`` package is GPL-3.0 (cannot
be used, docs/conventions.md) and statsmodels/scipy would add heavy numeric
dependencies for four short formulas. Each function is tested against
published worked examples (see tests/test_agreement_stats.py).

A statistic that is undefined for the data (for example kappa when both
raters always give the same single value, so expected agreement is 1) is
returned as None rather than a misleading number.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Hashable, Mapping, Sequence
from itertools import combinations


class AgreementError(ValueError):
    """Raised when ratings are not shaped as a statistic requires."""


def cohen_kappa(rater_a: Sequence[Hashable], rater_b: Sequence[Hashable]) -> float | None:
    """Cohen's kappa for two raters labelling the same items.

    kappa = (p_o - p_e) / (1 - p_e), where p_o is observed agreement and p_e
    the agreement expected from each rater's own label frequencies.

    Args:
        rater_a: Labels from the first rater, one per item.
        rater_b: Labels from the second rater for the same items, same order.

    Returns:
        Kappa, or None when p_e is 1 (both raters used one and the same
        label throughout), where kappa is undefined.

    Raises:
        AgreementError: If the sequences differ in length or are empty.
    """
    if len(rater_a) != len(rater_b):
        raise AgreementError("both raters must label the same items")
    if not rater_a:
        raise AgreementError("no items to compare")
    total = len(rater_a)

    # Observed agreement, then chance agreement from the marginal frequencies.
    observed = sum(a == b for a, b in zip(rater_a, rater_b, strict=True)) / total
    counts_a, counts_b = Counter(rater_a), Counter(rater_b)
    expected = sum(counts_a[label] * counts_b[label] for label in counts_a) / (total * total)
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1.0 - expected)


def fleiss_kappa(counts: Sequence[Sequence[int]]) -> float | None:
    """Fleiss' kappa from a subjects-by-categories table of rating counts.

    Args:
        counts: One row per subject; ``counts[i][j]`` is how many raters put
            subject i in category j. Every row must sum to the same number of
            raters n >= 2.

    Returns:
        Kappa, or None when expected agreement is 1 (every rating in one
        category), where kappa is undefined.

    Raises:
        AgreementError: If the table is empty, ragged, has negative counts,
            or rows sum to different rater counts.
    """
    if not counts:
        raise AgreementError("no subjects")
    width = len(counts[0])
    if any(len(row) != width for row in counts) or any(c < 0 for row in counts for c in row):
        raise AgreementError("every row needs the same number of non-negative counts")
    raters = sum(counts[0])
    if raters < 2 or any(sum(row) != raters for row in counts):
        raise AgreementError("every subject needs the same number of raters, at least two")
    subjects = len(counts)

    # Mean per-subject agreement: the share of agreeing rater pairs per subject.
    per_subject = [(sum(c * c for c in row) - raters) / (raters * (raters - 1)) for row in counts]
    observed = sum(per_subject) / subjects

    # Chance agreement from the overall category proportions.
    proportions = [sum(row[j] for row in counts) / (subjects * raters) for j in range(width)]
    expected = sum(p * p for p in proportions)
    if math.isclose(expected, 1.0):
        return None
    return (observed - expected) / (1.0 - expected)


def krippendorff_alpha_nominal(units: Sequence[Sequence[Hashable | None]]) -> float | None:
    """Krippendorff's alpha for nominal data; None marks a missing rating.

    Only pairable values count: a unit contributes when at least two of its
    values are present. alpha = 1 - D_o / D_e, computed through the
    coincidence matrix as in Krippendorff (2011).

    Args:
        units: One sequence per unit holding each rater's value (or None).
            Rater order does not matter for nominal alpha.

    Returns:
        Alpha, or None when fewer than two pairable values exist or every
        pairable value is identical (no variation, so D_e is 0).
    """
    # Coincidence matrix: each ordered pair of values within a unit, weighted 1/(m_u - 1).
    coincidences: defaultdict[tuple[Hashable, Hashable], float] = defaultdict(float)
    for unit in units:
        values = [v for v in unit if v is not None]
        m = len(values)
        if m < 2:
            continue
        for i, j in ((i, j) for i in range(m) for j in range(m) if i != j):
            coincidences[(values[i], values[j])] += 1.0 / (m - 1)

    # Marginals n_c and the total number of pairable values n.
    marginals: defaultdict[Hashable, float] = defaultdict(float)
    for (first, _), weight in coincidences.items():
        marginals[first] += weight
    total = sum(marginals.values())
    if total < 2:
        return None

    observed_disagreement = sum(w for (c, k), w in coincidences.items() if c != k)
    expected_pairs = sum(
        marginals[c] * marginals[k] for c in marginals for k in marginals if c != k
    )
    if math.isclose(expected_pairs, 0.0):
        return None
    return 1.0 - (total - 1.0) * observed_disagreement / expected_pairs


def kendall_tau_b(x: Sequence[float], y: Sequence[float]) -> float | None:
    """Kendall's tau-b rank correlation, corrected for ties in either variable.

    tau_b = (n_c - n_d) / sqrt((n_0 - n_1) (n_0 - n_2)), where n_0 counts all
    pairs and n_1, n_2 the pairs tied in x and in y. O(n^2), which is ample for
    the few hundred items in FactPICO.

    Args:
        x: First variable.
        y: Second variable, paired with ``x``.

    Returns:
        Tau-b, or None when either variable is constant (the denominator is 0).

    Raises:
        AgreementError: If the sequences differ in length or have fewer than
            two items.
    """
    if len(x) != len(y):
        raise AgreementError("x and y must have the same length")
    if len(x) < 2:
        raise AgreementError("need at least two pairs")

    concordant = discordant = tied_x = tied_y = 0
    for (x1, y1), (x2, y2) in combinations(zip(x, y, strict=True), 2):
        dx, dy = x1 - x2, y1 - y2
        # A pair tied in x (or y) counts towards that tie total and is neither
        # concordant nor discordant; a pair tied in both counts towards both.
        if dx == 0:
            tied_x += 1
        if dy == 0:
            tied_y += 1
        if dx != 0 and dy != 0:
            if (dx > 0) == (dy > 0):
                concordant += 1
            else:
                discordant += 1

    pairs = len(x) * (len(x) - 1) // 2
    denominator = math.sqrt((pairs - tied_x) * (pairs - tied_y))
    if denominator == 0:
        return None
    return (concordant - discordant) / denominator


def observed_agreement(units: Sequence[Sequence[Hashable | None]]) -> float | None:
    """Share of agreeing rater pairs, pooled over units (missing values skipped).

    Args:
        units: One sequence per unit holding each rater's value (or None).

    Returns:
        Agreeing pairs / all pairs, or None when no unit has two values.
    """
    agreeing = total = 0
    for unit in units:
        values = [v for v in unit if v is not None]
        for first, second in combinations(values, 2):
            total += 1
            agreeing += first == second
    return agreeing / total if total else None


def category_counts(
    units: Sequence[Sequence[Hashable | None]], categories: Sequence[Hashable]
) -> list[list[int]]:
    """Convert per-unit values into the count table :func:`fleiss_kappa` takes.

    Args:
        units: One sequence of values per unit (None = missing).
        categories: Every category, fixing the column order.

    Returns:
        One row of counts per unit.

    Raises:
        AgreementError: If a value is not one of ``categories``.
    """
    index: Mapping[Hashable, int] = {category: i for i, category in enumerate(categories)}
    table: list[list[int]] = []
    for unit in units:
        row = [0] * len(categories)
        for value in unit:
            if value is None:
                continue
            if value not in index:
                raise AgreementError(f"value {value!r} is not one of {list(categories)}")
            row[index[value]] += 1
        table.append(row)
    return table
