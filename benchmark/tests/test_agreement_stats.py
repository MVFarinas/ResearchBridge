"""Agreement statistics checked against published worked examples with known values."""

from __future__ import annotations

import pytest

from rbbench.agreement.stats import (
    AgreementError,
    category_counts,
    cohen_kappa,
    fleiss_kappa,
    kendall_tau_b,
    krippendorff_alpha_nominal,
    observed_agreement,
)


def _missing(value: str) -> int | None:
    """Parse one cell of a published reliability table; '*' and '.' mean missing."""
    return None if value in {"*", "."} else int(value)


def _units(*rows: str) -> list[list[int | None]]:
    """Turn coder-by-unit rows (as printed in the sources) into unit-by-coder lists."""
    table = [[_missing(cell) for cell in row.split()] for row in rows]
    return [list(unit) for unit in zip(*table, strict=True)]


def test_cohen_kappa_wikipedia_grant_example() -> None:
    """Cohen's kappa is 0.4 on the 50 grant proposals example.

    Source: Wikipedia, "Cohen's kappa", section "Simple example" (retrieved
    2026-10-13): readers A and B agree Yes 20, No 15; A Yes / B No 5;
    A No / B Yes 10; p_o = 0.7, p_e = 0.5, kappa = 0.4.
    """
    reader_a = ["yes"] * 20 + ["yes"] * 5 + ["no"] * 10 + ["no"] * 15
    reader_b = ["yes"] * 20 + ["no"] * 5 + ["yes"] * 10 + ["no"] * 15
    assert cohen_kappa(reader_a, reader_b) == pytest.approx(0.4)


def test_fleiss_kappa_wikipedia_psychiatrists_example() -> None:
    """Fleiss' kappa is 0.210 for 10 patients, 14 psychiatrists, 5 diagnoses.

    Source: Wikipedia, "Fleiss's kappa", section "Worked example" (retrieved
    2026-10-13): P-bar = 0.378, P-bar_e = 0.213, kappa = 0.210.
    """
    counts = [
        [0, 0, 0, 0, 14],
        [0, 2, 6, 4, 2],
        [0, 0, 3, 5, 6],
        [0, 3, 9, 2, 0],
        [2, 2, 8, 1, 1],
        [7, 7, 0, 0, 0],
        [3, 2, 6, 3, 0],
        [2, 5, 3, 2, 2],
        [6, 5, 2, 1, 0],
        [0, 2, 2, 3, 7],
    ]
    assert fleiss_kappa(counts) == pytest.approx(0.210, abs=5e-4)


def test_krippendorff_alpha_binary_two_observers() -> None:
    """Nominal alpha is 0.095 for the two-observer binary example.

    Source: Krippendorff, K. (2011). Computing Krippendorff's Alpha-Reliability.
    Annenberg School for Communication, University of Pennsylvania, section A
    (binary data, two observers, no missing data): alpha = 0.095.
    """
    units = _units("0 1 0 0 0 0 0 0 1 0", "1 1 1 0 0 1 0 0 0 0")
    assert krippendorff_alpha_nominal(units) == pytest.approx(0.095, abs=5e-4)


def test_krippendorff_alpha_nominal_four_observers_missing_data() -> None:
    """Nominal alpha is 0.743 for four observers, 12 units, with missing data.

    Source: Krippendorff (2011), Computing Krippendorff's Alpha-Reliability,
    section C (nominal data, any number of observers, missing data):
    alpha = 0.743.
    """
    units = _units(
        "1 2 3 3 2 1 4 1 2 . . .",
        "1 2 3 3 2 2 4 1 2 5 . 3",
        ". 3 3 3 2 3 4 2 2 5 1 .",
        "1 2 3 3 2 4 4 1 2 5 1 .",
    )
    assert krippendorff_alpha_nominal(units) == pytest.approx(0.743, abs=5e-4)


def test_krippendorff_alpha_wikipedia_three_coders() -> None:
    """Nominal alpha is 0.691 for the 3-coder, 15-unit computational example.

    Source: Wikipedia, "Krippendorff's alpha", section "A computational
    example" (retrieved 2026-10-13): n = 26 pairable values, alpha_nominal =
    0.691.
    """
    units = _units(
        "* * * * * 3 4 1 2 1 1 3 3 * 3",
        "1 * 2 1 3 3 4 3 * * * * * * *",
        "* * 2 1 3 4 4 * 2 1 1 3 3 * 4",
    )
    assert krippendorff_alpha_nominal(units) == pytest.approx(0.691, abs=5e-4)


def test_kendall_tau_b_scipy_documentation_example() -> None:
    """Tau-b is -0.47140452 for the example in SciPy's kendalltau documentation.

    Source: SciPy reference, scipy.stats.kendalltau, "Examples" (x1 = [12, 2,
    1, 12, 2], x2 = [1, 4, 7, 1, 0], statistic -0.47140452079103173). The data
    has ties in both variables, so this exercises the tie correction.
    """
    assert kendall_tau_b([12, 2, 1, 12, 2], [1, 4, 7, 1, 0]) == pytest.approx(
        -0.47140452079103173, rel=1e-12
    )


def test_kendall_tau_b_perfect_and_reversed_orderings() -> None:
    """Identical rankings give 1 and reversed rankings give -1."""
    assert kendall_tau_b([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert kendall_tau_b([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_undefined_statistics_return_none() -> None:
    """Statistics without variation are undefined (None), not a misleading number."""
    assert cohen_kappa(["no", "no", "no"], ["no", "no", "no"]) is None
    assert fleiss_kappa([[3, 0], [3, 0]]) is None
    assert krippendorff_alpha_nominal([["no", "no"], ["no", "no"]]) is None
    assert krippendorff_alpha_nominal([["no", None], [None, "yes"]]) is None
    assert kendall_tau_b([1, 1, 1], [1, 2, 3]) is None


def test_two_rater_alpha_differs_from_cohen_only_by_expected_agreement() -> None:
    """With two raters and full data, perfect agreement gives 1 for both statistics."""
    first = ["a", "b", "a", "c"]
    assert cohen_kappa(first, first) == pytest.approx(1.0)
    assert krippendorff_alpha_nominal([[v, v] for v in first]) == pytest.approx(1.0)


def test_invalid_shapes_raise() -> None:
    """Mismatched or empty inputs raise AgreementError."""
    with pytest.raises(AgreementError):
        cohen_kappa(["a"], ["a", "b"])
    with pytest.raises(AgreementError):
        cohen_kappa([], [])
    with pytest.raises(AgreementError):
        fleiss_kappa([[2, 0], [1, 0]])
    with pytest.raises(AgreementError):
        fleiss_kappa([[1, 0]])
    with pytest.raises(AgreementError):
        kendall_tau_b([1.0], [2.0])


def test_category_counts_and_observed_agreement() -> None:
    """Count tables skip missing values; observed agreement pools rater pairs."""
    units: list[list[str | None]] = [["yes", "yes", None], ["yes", "no", "no"]]
    assert category_counts(units, ["no", "yes"]) == [[0, 2], [2, 1]]
    # Pairs: unit 1 (yes, yes) agree; unit 2 has 3 pairs, 1 agreeing: 2 / 4.
    assert observed_agreement(units) == pytest.approx(0.5)
    with pytest.raises(AgreementError):
        category_counts([["maybe"]], ["no", "yes"])
