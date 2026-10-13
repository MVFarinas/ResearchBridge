"""Tests for validation 1's method, summary and report tables (synthetic pairs only)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from spacy.language import Language

from rbcore.http import PoliteFetcher
from rbscores.familiarity import WordfreqFamiliarity
from rbscores.readability.composite import ReferenceStats, load_reference
from rbscores.readability.features import FEATURE_NAMES
from rbscores.validation1 import workflow
from rbscores.validation1.dataset import LayPair
from rbscores.validation1.render import render_medians, render_tables
from rbscores.validation1.run import (
    METRICS,
    PairResult,
    TextMetrics,
    compare,
    evaluate_pair,
    failure_analysis,
    summarise,
    truncate_to_words,
)

# Texts written for these tests (SYNTHETIC, not from any dataset).
SYNTHETIC_TECHNICAL = (
    "Pharmacological inhibition of mTORC1 attenuated phosphorylation of S6K1 in hepatocytes, "
    "as quantified by immunoblotting of lysates."
)
SYNTHETIC_PLAIN = (
    "The drug blocked a growth signal in liver cells. We checked this with a simple lab test. "
    "The signal fell a lot."
)


def _metrics(composite: float, burden: float, words: int = 100) -> TextMetrics:
    """Build synthetic metrics with given composite and burden values."""
    values = dict.fromkeys(METRICS, 1.0) | {"composite": composite, "burden": burden}
    return TextMetrics(
        words=words,
        values=values,
        z_scores=dict.fromkeys(FEATURE_NAMES, composite),
        undefined_terms=0,
        defined_terms=0,
    )


def _result(pair_id: str, source: str, lay: TextMetrics, technical: TextMetrics) -> PairResult:
    """Build a synthetic pair result (matched = full)."""
    pair = LayPair(pair_id, source, "validation", 0, f"Synthetic {pair_id}", "2020", "a", "b")
    return PairResult(pair, lay, technical, lay, technical)


def test_truncate_to_words_cuts_at_the_nearest_sentence_boundary(nlp: Language) -> None:
    """The prefix of whole sentences closest to the target is kept."""
    text = "One two three. Four five six seven. Eight nine."
    assert truncate_to_words(text, 3, nlp=nlp) == "One two three."
    assert truncate_to_words(text, 6, nlp=nlp) == "One two three. Four five six seven."
    assert truncate_to_words(text, 1, nlp=nlp) == "One two three."
    assert truncate_to_words(text, 100, nlp=nlp) == text


def test_evaluate_pair_ranks_plain_text_easier(nlp: Language) -> None:
    """On a clear synthetic pair, the composite and burden both rank the plain text easier."""
    pair = LayPair(
        "synthetic-1",
        "elife",
        "validation",
        0,
        "Synthetic",
        "2020",
        SYNTHETIC_TECHNICAL,
        SYNTHETIC_PLAIN,
    )
    result = evaluate_pair(
        pair, nlp=nlp, familiarity=WordfreqFamiliarity(), reference=load_reference()
    )
    assert result is not None
    assert result.lay.values["composite"] < result.technical.values["composite"]
    assert result.lay.values["burden"] < result.technical.values["burden"]
    assert set(result.lay.values) == set(METRICS)

    # Length matching cuts the longer (plain) text to whole sentences nearer the shorter one.
    assert result.lay.words > result.technical.words
    assert result.technical_matched == result.technical
    assert result.lay_matched.words < result.lay.words
    gap_matched = abs(result.lay_matched.words - result.technical.words)
    assert gap_matched < result.lay.words - result.technical.words


def test_evaluate_pair_skips_empty_texts(
    nlp: Language, synthetic_reference: ReferenceStats
) -> None:
    """A pair with a wordless text cannot be compared."""
    pair = LayPair("synthetic-2", "plos", "validation", 0, "S", "2020", "...", SYNTHETIC_PLAIN)
    assert (
        evaluate_pair(
            pair, nlp=nlp, familiarity=WordfreqFamiliarity(), reference=synthetic_reference
        )
        is None
    )


def test_compare_counts_correct_pairs_and_ties() -> None:
    """Share correct counts strict lay < technical; ties are reported and count as wrong."""
    results = [
        _result("1", "elife", _metrics(-1.0, 10), _metrics(1.0, 20)),
        _result("2", "elife", _metrics(-1.0, 30), _metrics(1.0, 20)),
        _result("3", "elife", _metrics(2.0, 20), _metrics(1.0, 20)),
        _result("4", "elife", _metrics(0.0, 5), _metrics(0.5, 20)),
    ]
    composite = compare(results, "composite", "full")
    assert (composite["n"], composite["lay_easier"], composite["ties"]) == (4, 3, 0)
    assert composite["share_correct"] == 0.75
    assert composite["ci95_low"] < 0.75 < composite["ci95_high"]
    burden = compare(results, "burden", "full")
    assert (burden["lay_easier"], burden["ties"]) == (2, 1)
    # Differences -10, 10, 0, -15: median -5.
    assert burden["median_difference"] == pytest.approx(-5.0)


def test_failure_analysis_and_summary() -> None:
    """Failures are counted and explained; the summary groups by corpus and pools."""
    results = [
        _result("1", "elife", _metrics(-1.0, 10), _metrics(1.0, 20)),
        _result("2", "plos", _metrics(2.0, 30, words=300), _metrics(1.0, 20)),
    ]
    analysis = failure_analysis(results)
    assert analysis["composite_failures"] == 1
    assert analysis["failures_also_failing_burden"] == 1
    assert analysis["failures_with_longer_lay_text"] == 1
    assert analysis["worst_examples"][0]["id"] == "2"
    assert analysis["median_feature_z_difference_in_failures"]["passive_rate"] == pytest.approx(1.0)

    summary = summarise(results, metadata={"reference_version": "synthetic"})
    assert summary["provisional"] is True
    assert summary["pairs"] == {"elife": 1, "plos": 1, "all": 2}
    assert summary["comparisons"]["full"]["all"]["composite"]["lay_easier"] == 1
    assert json.loads(json.dumps(summary)) == summary

    tables = render_tables(summary)
    assert "| **Composite readability** | 100.0% [" in tables
    assert "Pooled (n = 2)" in tables
    assert "| eLife | 100 | 100 | 100 | 100 |" in tables
    assert "eLife lay | eLife abstract" in render_medians(summary)


def test_workflow_download_calibrate_and_run(synthetic_hub: PoliteFetcher, tmp_path: Path) -> None:
    """End to end on the synthetic hub: files are written and every pair is scored."""
    data_dir = tmp_path / "data"
    manifest = workflow.download(
        data_dir, sources=["elife"], calibration_rows=10, fetcher=synthetic_hub
    )
    assert manifest["sources"]["elife"]["pairs"] == 2
    assert manifest["sources"]["elife"]["skipped_rows"] == [1]
    assert manifest["sources"]["elife"]["revision"] == "synthetic-sha"
    assert manifest["sources"]["elife"]["calibration_articles"] == 2
    assert manifest["sources"]["elife"]["calibration_windows"] == 4

    reference = workflow.calibrate(data_dir, tmp_path / "ref.json", version="synthetic-v")
    assert reference.units == 4
    assert json.loads((tmp_path / "ref.json").read_text())["version"] == "synthetic-v"

    results = workflow.run(data_dir, sources=["elife"], log=lambda _: None)
    assert results["pairs"] == {"elife": 2, "all": 2}
    assert results["comparisons"]["full"]["elife"]["composite"]["lay_easier"] == 2
    assert results["dataset"]["elife"]["dataset"] == "BioLaySumm/BioLaySumm2025-eLife"
    assert (data_dir / "validation1" / "per-pair.jsonl").read_text().count("\n") == 2
