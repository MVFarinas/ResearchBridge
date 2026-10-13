"""Validation of lay comprehension question sets (``benchmark/comprehension/``).

The JSON Schema (``schema_v1.json``) is the contract; this module applies it
and adds the checks a schema cannot express: unique passage and question IDs,
answer keys that point at real options, and the right answer shape per
question type. No questions are written here; see the README in that folder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from rbbench.paths import COMPREHENSION_DIR

SCHEMA_PATH = COMPREHENSION_DIR / "schema_v1.json"


def load_schema(path: Path = SCHEMA_PATH) -> dict[str, Any]:
    """Load the JSON Schema and check that it is itself a valid schema.

    Args:
        path: The schema file.

    Returns:
        The schema.

    Raises:
        jsonschema.exceptions.SchemaError: If the schema is malformed.
    """
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_question_set(document: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Validate a question set.

    Args:
        document: The parsed YAML or JSON document.
        schema: The schema; the committed schema_v1 when None.

    Returns:
        Error messages; empty when the document is valid.
    """
    validator = Draft202012Validator(schema or load_schema())
    errors = [
        f"{'/'.join(str(p) for p in error.absolute_path) or '<root>'}: {error.message}"
        for error in sorted(validator.iter_errors(document), key=lambda e: list(e.absolute_path))
    ]
    if errors:
        return errors
    return _semantic_errors(document)


def _semantic_errors(document: dict[str, Any]) -> list[str]:
    """Check what the schema cannot: unique IDs and consistent answer keys.

    Args:
        document: A schema-valid question set.

    Returns:
        Error messages.
    """
    errors: list[str] = []
    passage_ids = [p["passage_id"] for p in document["passages"]]
    if len(passage_ids) != len(set(passage_ids)):
        errors.append("passage IDs must be unique")
    for passage in document["passages"]:
        seen: set[str] = set()
        for question in passage["questions"]:
            qid = f"{passage['passage_id']}/{question['question_id']}"
            if question["question_id"] in seen:
                errors.append(f"{qid}: duplicate question ID")
            seen.add(question["question_id"])
            option_ids = [o["id"] for o in question["options"]]
            correct = question["correct_option_ids"]
            # Closed questions need options and a key that points at them.
            if question["type"] == "short_answer":
                if option_ids or correct:
                    errors.append(f"{qid}: short answers take no options or option key")
                if not question.get("answer_key"):
                    errors.append(f"{qid}: short answers need an answer_key")
            else:
                if len(option_ids) < 2 or len(option_ids) != len(set(option_ids)):
                    errors.append(f"{qid}: needs at least two options with unique IDs")
                if not correct or any(c not in option_ids for c in correct):
                    errors.append(f"{qid}: correct_option_ids must name existing options")
    return errors


def validate_file(path: Path) -> list[str]:
    """Validate a YAML or JSON question-set file.

    Args:
        path: The file.

    Returns:
        Error messages; empty when valid.
    """
    text = path.read_text(encoding="utf-8")
    document = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    return validate_question_set(document)
