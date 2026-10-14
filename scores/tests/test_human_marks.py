"""Tests for the term-marks format, its validator and its evaluation (synthetic data)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from spacy.language import Language

from rbscores.familiarity import WordfreqFamiliarity
from rbscores.human_data.common import HumanDataError
from rbscores.human_data.marks import (
    PassageTerm,
    PassageTerms,
    analyse_passages,
    evaluate_marks_against,
    load_marks,
    parse_marks,
)


@pytest.fixture
def synthetic_marks_data(repo_root: Path) -> dict[str, Any]:
    """The documented SYNTHETIC term-marks example, as parsed JSON."""
    path = repo_root / "docs" / "data-formats" / "examples" / "term-marks.synthetic.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _problems(data: Any) -> tuple[str, ...]:
    """Return the validator's problems for a document (empty if valid)."""
    try:
        parse_marks(data)
    except HumanDataError as exc:
        return exc.problems
    return ()


def test_documented_example_is_valid(repo_root: Path) -> None:
    """The example in docs/data-formats loads, with marks sorted and checked."""
    study = load_marks(
        repo_root / "docs" / "data-formats" / "examples" / "term-marks.synthetic.json"
    )
    assert study.header.synthetic is True
    assert len(study.responses) == 4
    assert study.responses[1].marks == ()
    assert [m.text for m in study.responses[2].marks] == ["Apoptosis", "hepatocytes"]
    assert "4 responses, 4 marks" in study.summary()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["responses"][0]["marks"][0].update(end=99), "offsets"),
        (lambda d: d["responses"][0]["marks"][0].update(start=50), "offsets"),
        (lambda d: d["responses"][0]["marks"][0].update(text="kidney"), "does not match"),
        (lambda d: d["responses"][0]["marks"][0].update(start=True), "offsets"),
        (
            lambda d: d["responses"][0]["marks"].append({"start": 36, "end": 40, "text": "phro"}),
            "overlapping",
        ),
        (lambda d: d["responses"][0].pop("marks"), "must be a list"),
        (lambda d: d["responses"].append(dict(d["responses"][0])), "repeats rater"),
        (lambda d: d["responses"][0].update(passage_id="zz"), "listed passage"),
        (lambda d: d.update(schema="researchbridge.pairwise-judgements"), "'schema' must be"),
    ],
)
def test_validator_reports_problems(
    synthetic_marks_data: dict[str, Any], mutate: Any, message: str
) -> None:
    """Each kind of invalid input is reported with a clear message."""
    data = copy.deepcopy(synthetic_marks_data)
    mutate(data)
    problems = _problems(data)
    assert any(message in p for p in problems), problems


def test_evaluation_against_hand_built_terms(synthetic_marks_data: dict[str, Any]) -> None:
    """Mark rates, precision, recall and correlations follow the definitions exactly."""
    study = parse_marks(synthetic_marks_data)
    # SYNTHETIC pipeline output: offsets refer to the example passages.
    passages = {
        "m1": PassageTerms("m1", 11, 50.0, (PassageTerm("nephron", 0.9, ((34, 42),)),)),
        "m2": PassageTerms(
            "m2",
            8,
            100.0,
            (
                PassageTerm("apoptosis", 0.0, ((0, 9),)),
                PassageTerm("hepatocyte", 1.0, ((53, 64),)),
                PassageTerm("cell death", 0.2, ((25, 35),)),
            ),
        ),
    }
    result = evaluate_marks_against(study, passages)
    assert (result["responses"], result["marks"]) == (4, 4)

    # Mark rates: nephron 1/2, apoptosis 1/2, hepatocyte 2/2, cell death 0/2.
    term_level = result["term_level"]
    assert term_level["candidate_terms"] == 4
    # Majority-marked weights 0.9, 0.0, 1.0 against 0.2: two of three pairs ordered.
    assert term_level["auc_weight_for_majority_marked"] == pytest.approx(2 / 3)
    assert term_level["spearman_weight_vs_mark_rate"] > 0

    # Flagged terms (weight > 0): nephron, hepatocyte, cell death.
    quality = result["list_quality"]
    assert quality["flagged_terms"] == 3
    assert quality["precision_marked_by_any"] == pytest.approx(2 / 3)
    assert quality["precision_marked_by_most"] == pytest.approx(2 / 3)
    assert quality["recall_of_marks_by_flagged_terms"] == pytest.approx(3 / 4)
    assert quality["recall_of_marks_by_any_candidate"] == 1.0

    # Passage level: m1 has 0.5 marks over 11 words, m2 1.5 over 8; burden 50 vs 100.
    assert result["passage_level"]["passages"] == 2
    assert result["passage_level"]["spearman_burden_vs_marks_per_1000"] == pytest.approx(1.0)


def test_analyse_passages_keeps_exact_offsets(
    synthetic_marks_data: dict[str, Any], nlp: Language
) -> None:
    """The real pipeline's term spans index the passage text, and defined terms weigh 0."""
    study = parse_marks(synthetic_marks_data)
    views = analyse_passages(study, nlp=nlp, familiarity=WordfreqFamiliarity())
    m1 = views["m1"]
    text = study.header.passages["m1"].text
    nephron = next(t for t in m1.terms if t.key == "nephron")
    assert [text[a:b] for a, b in nephron.spans] == ["nephrons"]
    assert nephron.weight > 0.5

    # "Apoptosis, or programmed cell death," defines apoptosis in m2.
    apoptosis = next(t for t in views["m2"].terms if t.key == "apoptosis")
    assert apoptosis.weight == 0.0
    assert views["m2"].burden_per_1000 > 0
