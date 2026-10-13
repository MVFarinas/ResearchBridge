"""Markdown tables for the validation 1 report, rendered from the results JSON.

The narrative in scores/reports/validation_1.md is written by hand; the
numbers in its tables come from here, so they are never retyped.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rbscores.validation1.run import COMPARISONS, METRICS

_GROUP_LABELS = {"elife": "eLife", "plos": "PLOS", "all": "Pooled"}
_METRIC_LABELS = {
    "mean_sentence_length": "Sentence length",
    "mean_parse_depth": "Syntactic depth",
    "nominalisation_rate": "Nominalisation rate",
    "passive_rate": "Passive-voice rate",
    "jargon_density": "Jargon density",
    "composite": "**Composite readability**",
    "burden": "**Burden**",
    "burden_no_definitions": "Burden, definitions ignored (ablation)",
    "flesch_kincaid_grade": "Flesch-Kincaid grade (baseline, not ours)",
}
_COMPARISON_TITLES = {
    "full": "Full texts",
    "length_matched": "Length-matched (longer text cut to whole sentences)",
}


def render_tables(results: Mapping[str, Any]) -> str:
    """Render the comparison and word-count tables.

    Args:
        results: The document produced by :func:`rbscores.validation1.run.summarise`.

    Returns:
        Markdown text.
    """
    groups = [g for g in ("elife", "plos", "all") if g in results["pairs"]]
    lines: list[str] = []

    # One table per comparison: share of pairs ranked correctly, per group.
    for comparison in COMPARISONS:
        lines.append(f"#### {_COMPARISON_TITLES[comparison]}")
        lines.append("")
        header = ["Metric"] + [f"{_GROUP_LABELS[g]} (n = {results['pairs'][g]})" for g in groups]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("|" + "---|" * len(header))
        for metric in METRICS:
            cells = [_METRIC_LABELS[metric]]
            for group in groups:
                cells.append(_share_cell(results["comparisons"][comparison][group][metric]))
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")

    # Paired comparisons: exact McNemar tests on the same pairs.
    lines.append("#### Paired comparisons (exact McNemar test on discordant pairs)")
    lines.append("")
    lines.append("| Comparison | Group | Both right | Only first | Only second | Neither | p |")
    lines.append("|---|---|---|---|---|---|---|")
    for comparison in COMPARISONS:
        for group in groups:
            for row in results["paired"][comparison][group]:
                label = (
                    f"{_plain(row['first'])} vs {_plain(row['second'])}, "
                    f"{'full' if comparison == 'full' else 'matched'}"
                )
                counts = [row[k] for k in ("both", "only_first", "only_second", "neither")]
                cells = [label, _GROUP_LABELS[group], *map(str, counts)]
                cells.append(_p_value(row["mcnemar_exact_p"]))
                lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Median word counts, to show what length matching did.
    lines.append("#### Median word counts")
    lines.append("")
    lines.append("| Group | Lay | Abstract | Lay, matched | Abstract, matched |")
    lines.append("|---|---|---|---|---|")
    for group in groups:
        words = results["words"][group]
        counts = [
            _number(words[key], 0)
            for key in (
                "lay_median",
                "technical_median",
                "matched_lay_median",
                "matched_technical_median",
            )
        ]
        lines.append(f"| {_GROUP_LABELS[group]} | " + " | ".join(counts) + " |")
    lines.append("")

    # How many terms the burden pipeline counts and removes as defined.
    lines.append("#### Median term counts per text (full texts)")
    lines.append("")
    lines.append("| Group | Lay undefined | Abstract undefined | Lay defined | Abstract defined |")
    lines.append("|---|---|---|---|---|")
    for group in groups:
        terms = results["terms"][group]
        values = [
            _number(terms[key], 0)
            for key in ("lay_undefined", "technical_undefined", "lay_defined", "technical_defined")
        ]
        lines.append(f"| {_GROUP_LABELS[group]} | " + " | ".join(values) + " |")
    lines.append("")
    return "\n".join(lines)


def render_medians(results: Mapping[str, Any], comparison: str = "full") -> str:
    """Render median metric values for lay and technical texts.

    Args:
        results: The results document.
        comparison: "full" or "length_matched".

    Returns:
        Markdown text.
    """
    groups = [g for g in ("elife", "plos") if g in results["pairs"]]
    header = ["Metric"]
    for group in groups:
        header += [f"{_GROUP_LABELS[group]} lay", f"{_GROUP_LABELS[group]} abstract"]
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for metric in METRICS:
        cells = [_METRIC_LABELS[metric]]
        for group in groups:
            row = results["comparisons"][comparison][group][metric]
            cells += [_number(row["median_lay"], 2), _number(row["median_technical"], 2)]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _share_cell(row: Mapping[str, Any]) -> str:
    """Format a share-correct cell: percentage, interval and ties.

    Args:
        row: One metric's comparison summary.

    Returns:
        For example "93.4% [91.1, 95.1]" plus "; 3 ties" when there are ties.
    """
    cell = (
        f"{100 * row['share_correct']:.1f}% "
        f"[{100 * row['ci95_low']:.1f}, {100 * row['ci95_high']:.1f}]"
    )
    if row["ties"]:
        cell += f"; {row['ties']} ties"
    return cell


def _plain(metric: str) -> str:
    """Return a metric's label without markdown emphasis.

    Args:
        metric: Metric name.

    Returns:
        The label, e.g. "Composite readability".
    """
    return _METRIC_LABELS[metric].replace("**", "")


def _p_value(value: float) -> str:
    """Format a p-value compactly.

    Args:
        value: The p-value.

    Returns:
        "< 0.001" for small values, else three decimals.
    """
    return "< 0.001" if value < 0.001 else f"{value:.3f}"


def _number(value: float | None, places: int) -> str:
    """Format a number, or an en dash for a missing value.

    Args:
        value: The number or None.
        places: Decimal places.

    Returns:
        The formatted value.
    """
    return "\u2013" if value is None else f"{value:.{places}f}"
