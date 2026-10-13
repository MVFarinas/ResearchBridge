"""Tests of the comprehension question-set schema and validator.

The questions below are SYNTHETIC placeholders for testing the validator;
they are not study questions.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from rbbench.comprehension import load_schema, validate_file, validate_question_set
from rbbench.paths import COMPREHENSION_DIR

TEMPLATE = COMPREHENSION_DIR / "template_v1.yaml"


def _template() -> dict[str, Any]:
    """The committed template, parsed."""
    document: dict[str, Any] = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    return document


def _synthetic_question(**overrides: Any) -> dict[str, Any]:
    """A SYNTHETIC multiple-choice question for validator tests."""
    question = {
        "question_id": "q1",
        "type": "multiple_choice",
        "stem": "SYNTHETIC test stem?",
        "targets": "population",
        "options": [{"id": "a", "text": "A"}, {"id": "b", "text": "B"}],
        "correct_option_ids": ["a"],
        "rationale": None,
    }
    question.update(overrides)
    return question


def _final(questions: list[dict[str, Any]], ethics: str = "approved") -> dict[str, Any]:
    """A FINAL document built from the template with the given questions."""
    document = copy.deepcopy(_template())
    document["status"] = "FINAL"
    document["study"]["ethics"]["status"] = ethics
    document["passages"][0]["questions"] = questions
    return document


def test_schema_is_valid_and_template_validates() -> None:
    """The schema is a valid draft 2020-12 schema; the template passes it."""
    assert load_schema()["$schema"].endswith("2020-12/schema")
    assert validate_file(TEMPLATE) == []
    assert _template()["jargon_marking"]["format"] == "defined by Track R (scores/)"
    assert _template()["passages"][0]["questions"] == []


def test_final_needs_questions_and_an_ethics_decision() -> None:
    """FINAL without questions, or with ethics not checked, is invalid."""
    assert validate_question_set(_final([])) != []
    assert any(
        "ethics" in e for e in validate_question_set(_final([_synthetic_question()], "not_checked"))
    )
    assert validate_question_set(_final([_synthetic_question()])) == []
    assert validate_question_set(_final([_synthetic_question()], "not_required")) == []


@pytest.mark.parametrize(
    ("questions", "message"),
    [
        ([_synthetic_question(correct_option_ids=["z"])], "must name existing options"),
        ([_synthetic_question(), _synthetic_question()], "duplicate question ID"),
        ([_synthetic_question(options=[{"id": "a", "text": "A"}])], "at least two options"),
        ([_synthetic_question(type="short_answer")], "take no options"),
        (
            [_synthetic_question(type="short_answer", options=[], correct_option_ids=[])],
            "need an answer_key",
        ),
    ],
)
def test_semantic_rules(questions: list[dict[str, Any]], message: str) -> None:
    """Answer keys, unique IDs and question-type shapes are checked."""
    errors = validate_question_set(_final(questions))
    assert any(message in e for e in errors), errors


def test_arms_are_fixed_and_unknown_fields_rejected(tmp_path: Path) -> None:
    """The three arms cannot be changed and stray fields are refused."""
    document = copy.deepcopy(_template())
    document["arms"] = ["original", "llm_rewrite"]
    assert validate_question_set(document) != []
    document = copy.deepcopy(_template())
    document["extra"] = 1
    assert validate_question_set(document) != []
    path = tmp_path / "set.json"
    path.write_text('{"schema_version": "comprehension_v1"}', encoding="utf-8")
    assert validate_file(path) != []
