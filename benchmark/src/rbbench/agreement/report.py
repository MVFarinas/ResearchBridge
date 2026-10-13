"""Per-code inter-rater agreement over a set of ratings.

For every rubric code (rated and derived) this computes, over the units the
code applies to: the number of units and raters, pooled pairwise observed
agreement, Cohen's kappa (two raters; with more, the mean over rater pairs),
Fleiss' kappa (over units rated by the full set of raters), Krippendorff's
alpha for nominal data (all pairable values, missing allowed) and the value
distribution, because kappa on a rare code is unstable and readers need the
prevalence to interpret it (decisions.md §1.4).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from rbbench.agreement.stats import (
    category_counts,
    cohen_kappa,
    fleiss_kappa,
    krippendorff_alpha_nominal,
    observed_agreement,
)
from rbbench.ratings import Rating
from rbbench.rubric import Rubric, Unit


class RatingsError(ValueError):
    """Raised when ratings are inconsistent (for example two ratings of one unit by one rater)."""


@dataclass(frozen=True, slots=True)
class CodeAgreement:
    """Agreement statistics for one code.

    Attributes:
        code_id: The code.
        unit: Claim or paragraph.
        derived: True for a computed code such as "overgeneralisation".
        raters: Rater IDs that rated at least one unit.
        n_units: Units with at least two ratings (the pairable units).
        observed_agreement: Share of agreeing rater pairs, pooled.
        cohen_kappa: Cohen's kappa (two raters) or the mean pairwise kappa
            over rater pairs with defined kappa (three or more).
        fleiss_kappa: Fleiss' kappa over units rated by every rater.
        fleiss_units: Units included in Fleiss' kappa.
        krippendorff_alpha: Nominal alpha over all pairable values.
        value_counts: How often each value was given, over all ratings.
        notes: Why a statistic is missing, or how it was computed.
    """

    code_id: str
    unit: Unit
    derived: bool
    raters: tuple[str, ...]
    n_units: int
    observed_agreement: float | None
    cohen_kappa: float | None
    fleiss_kappa: float | None
    fleiss_units: int
    krippendorff_alpha: float | None
    value_counts: dict[str, int]
    notes: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict of every field.
        """
        return {
            "code_id": self.code_id,
            "unit": self.unit.value,
            "derived": self.derived,
            "raters": list(self.raters),
            "n_units": self.n_units,
            "observed_agreement": self.observed_agreement,
            "cohen_kappa": self.cohen_kappa,
            "fleiss_kappa": self.fleiss_kappa,
            "fleiss_units": self.fleiss_units,
            "krippendorff_alpha": self.krippendorff_alpha,
            "value_counts": self.value_counts,
            "notes": list(self.notes),
        }


def labels_by_unit(
    ratings: Sequence[Rating], rubric: Rubric, unit: Unit
) -> dict[str, dict[str, dict[str, str]]]:
    """Index ratings as unit ID -> rater ID -> labels, with derived codes added.

    Args:
        ratings: Ratings of any unit type; other units are ignored.
        rubric: The rubric, used to compute derived codes.
        unit: Which unit type to index.

    Returns:
        Nested mapping; each labels dict holds rated and derived codes.

    Raises:
        RatingsError: If one rater rated the same unit twice.
    """
    index: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for rating in ratings:
        if rating.unit is not unit:
            continue
        if rating.rater_id in index[rating.unit_id]:
            raise RatingsError(f"rater {rating.rater_id!r} rated {rating.unit_id!r} twice")
        labels = dict(rating.labels)
        labels.update(rubric.derive(unit, rating.labels))
        index[rating.unit_id][rating.rater_id] = labels
    return dict(index)


def agreement_report(ratings: Sequence[Rating], rubric: Rubric) -> list[CodeAgreement]:
    """Compute agreement for every rated and derived code in the rubric.

    Args:
        ratings: Ratings from two or more raters.
        rubric: The rubric the ratings follow.

    Returns:
        One entry per code, rated codes first in rubric order, then derived.
    """
    report: list[CodeAgreement] = []
    for unit in Unit:
        index = labels_by_unit(ratings, rubric, unit)
        for code in rubric.codes_for(unit):
            report.append(_code_agreement(index, code.id, unit, code.value_ids, derived=False))
        for derived in rubric.derived:
            if derived.unit is unit:
                report.append(_code_agreement(index, derived.id, unit, ("no", "yes"), derived=True))
    return report


def _code_agreement(
    index: dict[str, dict[str, dict[str, str]]],
    code_id: str,
    unit: Unit,
    categories: Sequence[str],
    *,
    derived: bool,
) -> CodeAgreement:
    """Compute the statistics for one code from the unit index.

    Args:
        index: Unit ID -> rater ID -> labels.
        code_id: The code.
        unit: The code's unit.
        categories: The code's allowed values, fixing Fleiss' column order.
        derived: Whether the code is computed.

    Returns:
        The code's agreement entry.
    """
    raters = tuple(sorted({rater for by_rater in index.values() for rater in by_rater}))
    unit_ids = sorted(index)
    # One row per unit: each rater's value for this code, None where missing.
    rows = [[index[u].get(r, {}).get(code_id) for r in raters] for u in unit_ids]
    pairable = [row for row in rows if sum(v is not None for v in row) >= 2]
    notes: list[str] = []

    # Cohen: exact for two raters; mean of defined pairwise kappas for more.
    kappas: list[float] = []
    for i, j in combinations(range(len(raters)), 2):
        both = [(row[i], row[j]) for row in rows if row[i] is not None and row[j] is not None]
        if both:
            value = cohen_kappa([a for a, _ in both], [b for _, b in both])
            if value is not None:
                kappas.append(value)
    cohen = sum(kappas) / len(kappas) if kappas else None
    if len(raters) > 2 and kappas:
        notes.append(f"cohen_kappa is the mean over {len(kappas)} rater pairs")
    if cohen is None and pairable:
        notes.append("cohen_kappa undefined: no variation in a rater pair's labels")

    # Fleiss needs the same raters on every unit, so use fully rated units only.
    complete = [row for row in rows if all(v is not None for v in row)]
    fleiss = (
        fleiss_kappa(category_counts(complete, categories))
        if complete and len(raters) >= 2
        else None
    )
    if complete and fleiss is None and len(raters) >= 2:
        notes.append("fleiss_kappa undefined: every rating has the same value")

    alpha = krippendorff_alpha_nominal(pairable)
    if pairable and alpha is None:
        notes.append("krippendorff_alpha undefined: no variation in the pairable values")

    counts = Counter(v for row in rows for v in row if v is not None)
    return CodeAgreement(
        code_id=code_id,
        unit=unit,
        derived=derived,
        raters=raters,
        n_units=len(pairable),
        observed_agreement=observed_agreement(pairable),
        cohen_kappa=cohen,
        fleiss_kappa=fleiss,
        fleiss_units=len(complete),
        krippendorff_alpha=alpha,
        value_counts={value: counts.get(value, 0) for value in categories},
        notes=tuple(notes),
    )


def _fmt(value: float | None) -> str:
    """Format a statistic for a table; undefined values are shown as such.

    Args:
        value: The statistic or None.

    Returns:
        Three decimals, or "undefined".
    """
    return "undefined" if value is None else f"{value:.3f}"


def format_agreement_table(entries: Sequence[CodeAgreement]) -> str:
    """Render agreement entries as a Markdown table.

    Args:
        entries: Output of :func:`agreement_report`.

    Returns:
        The table, one row per code, with prevalence.
    """
    lines = [
        "| Code | Unit | Units | Raters | Observed | Cohen's κ | Fleiss' κ | Krippendorff's alpha "
        "| Values |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in entries:
        name = f"`{entry.code_id}`" + (" (derived)" if entry.derived else "")
        values = ", ".join(f"{k}: {v}" for k, v in entry.value_counts.items())
        lines.append(
            f"| {name} | {entry.unit.value} | {entry.n_units} | {len(entry.raters)} "
            f"| {_fmt(entry.observed_agreement)} | {_fmt(entry.cohen_kappa)} "
            f"| {_fmt(entry.fleiss_kappa)} | {_fmt(entry.krippendorff_alpha)} | {values} |"
        )
    return "\n".join(lines)
