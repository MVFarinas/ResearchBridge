"""Tests for the pairwise-judgement format, its validator and its evaluation (synthetic data)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from spacy.language import Language

from rbscores.human_data.common import HumanDataError
from rbscores.human_data.pairwise import (
    evaluate_pairwise,
    load_pairwise,
    parse_pairwise,
    rater_agreement,
    score_passages,
)
from rbscores.readability.composite import ReferenceStats


@pytest.fixture
def synthetic_study_data(repo_root: Path) -> dict[str, Any]:
    """The documented SYNTHETIC pairwise example, as parsed JSON."""
    path = repo_root / "docs" / "data-formats" / "examples" / "pairwise-judgements.synthetic.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def _problems(data: Any) -> tuple[str, ...]:
    """Return the validator's problems for a document (empty if valid)."""
    try:
        parse_pairwise(data)
    except HumanDataError as exc:
        return exc.problems
    return ()


def test_documented_example_is_valid(repo_root: Path) -> None:
    """The example in docs/data-formats loads and is flagged synthetic."""
    study = load_pairwise(
        repo_root / "docs" / "data-formats" / "examples" / "pairwise-judgements.synthetic.json"
    )
    assert study.header.synthetic is True
    assert len(study.judgements) == 5
    assert study.summary().endswith("3 passages, 3 raters, 5 judgements")
    assert "[SYNTHETIC]" in study.summary()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d.update(schema="other"), "'schema' must be"),
        (lambda d: d.update(version=2), "'version' must be 1"),
        (lambda d: d.pop("synthetic"), "'synthetic' must be true or false"),
        (lambda d: d["raters"][0].update(rater_id="jane@example.org"), "pseudonym"),
        (lambda d: d["raters"][0].update(background="phd"), "background must be one of"),
        (lambda d: d["passages"][1].update(passage_id="s1"), "duplicated"),
        (lambda d: d["judgements"][0].update(harder="maybe"), "harder must be one of"),
        (lambda d: d["judgements"][0].update(passage_b="s1"), "compares a passage with itself"),
        (lambda d: d["judgements"][0].update(passage_b="nope"), "not a listed passage"),
        (lambda d: d["judgements"][0].update(rater_id=["r01"]), "is not a listed rater"),
        (lambda d: d["judgements"][0].update(passage_a={"x": 1}), "not a listed passage"),
        (lambda d: d["judgements"][0].update(shown_first="c"), "shown_first"),
        (lambda d: d["judgements"].append(dict(d["judgements"][1])), "repeats rater"),
        (lambda d: d.update(judgements=[]), "'judgements' must be a non-empty list"),
    ],
)
def test_validator_reports_problems(
    synthetic_study_data: dict[str, Any], mutate: Any, message: str
) -> None:
    """Each kind of invalid input is reported with a clear message."""
    data = copy.deepcopy(synthetic_study_data)
    mutate(data)
    problems = _problems(data)
    assert any(message in p for p in problems), problems


def test_every_problem_is_reported_at_once(synthetic_study_data: dict[str, Any]) -> None:
    """Several independent problems all appear in one error."""
    data = copy.deepcopy(synthetic_study_data)
    data["version"] = 3
    data["judgements"][0]["harder"] = "x"
    data["judgements"][1]["rater_id"] = "ghost"
    assert len(_problems(data)) == 3


def test_load_rejects_non_json(tmp_path: Path) -> None:
    """A file that is not JSON gives a validation error, not a crash."""
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(HumanDataError, match="not valid UTF-8 JSON"):
        load_pairwise(path)


def test_evaluate_with_given_scores(synthetic_study_data: dict[str, Any]) -> None:
    """Agreement counts follow the judgements, majorities and ties exactly."""
    study = parse_pairwise(synthetic_study_data)
    # s2 is judged harder than s1 by all three raters; s2 harder than s3 by one.
    scores = {
        "good": {"s1": 1.0, "s2": 3.0, "s3": 2.0},
        "backwards": {"s1": 3.0, "s2": 1.0, "s3": 2.0},
        "flat": {"s1": 1.0, "s2": 1.0, "s3": 1.0},
    }
    result = evaluate_pairwise(study, scores)
    assert result["synthetic"] is True
    assert (result["judgements"], result["decisive_judgements"], result["pairs"]) == (5, 4, 3)
    assert result["pairs_with_majority"] == 2
    assert result["metrics"]["good"]["judgement_agreement"] == 1.0
    assert result["metrics"]["good"]["majority_agreement"] == 1.0
    assert result["metrics"]["backwards"]["judgement_agreement"] == 0.0
    assert result["metrics"]["flat"]["judgement_agreement"] == 0.0
    low, high = result["metrics"]["good"]["judgement_ci95"]
    assert 0.0 < low < 1.0
    assert high == pytest.approx(1.0)


def test_rater_agreement_compares_verdicts_regardless_of_order(
    synthetic_study_data: dict[str, Any],
) -> None:
    """Verdicts "a" and "b" agree when two raters saw the passages in opposite orders."""
    study = parse_pairwise(synthetic_study_data)
    agreement = rater_agreement(study.judgements)
    # Only the s1-s2 pair has several raters, and all three agree.
    assert agreement == {"pairs_with_multiple_raters": 1, "rater_pair_agreement": 1.0}


def test_score_passages_uses_the_provisional_metrics(
    synthetic_study_data: dict[str, Any], nlp: Language, synthetic_reference: ReferenceStats
) -> None:
    """Every passage gets every metric; the technical passage scores higher on burden."""
    study = parse_pairwise(synthetic_study_data)
    values = score_passages(study, nlp=nlp, reference=synthetic_reference)
    assert set(values) == {
        "mean_sentence_length",
        "mean_parse_depth",
        "nominalisation_rate",
        "passive_rate",
        "jargon_density",
        "composite",
        "burden",
    }
    assert values["burden"]["s2"] > values["burden"]["s1"]
    assert values["jargon_density"]["s2"] > values["jargon_density"]["s1"]
