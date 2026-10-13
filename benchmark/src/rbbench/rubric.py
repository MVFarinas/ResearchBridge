"""The machine-readable faithfulness rubric (``benchmark/rubric/rubric_v1.yaml``).

The rubric is the single definition of what raters, the LLM judge, the packet
form, the importer and the agreement statistics work with. Every code is
judged separately; derived codes (such as "overgeneralisation", any of the
three Peters & Chin-Yee shifts) are computed from rated codes and never rated
directly.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from rbbench.paths import RUBRIC_DIR

BINARY_VALUES = ("no", "yes")


class RubricError(ValueError):
    """Raised when a rubric file is invalid or labels do not fit the rubric."""


class Unit(StrEnum):
    """What a code is judged on."""

    CLAIM = "claim"
    PARAGRAPH = "paragraph"


@dataclass(frozen=True, slots=True)
class CodeValue:
    """One allowed value of a code.

    Attributes:
        id: Value identifier stored in ratings (e.g. "supported", "yes").
        label: Short label shown to raters.
        definition: When to choose it.
    """

    id: str
    label: str
    definition: str = ""


@dataclass(frozen=True, slots=True)
class RubricCode:
    """One rated code.

    Attributes:
        id: Code identifier (e.g. "lost_hedge").
        unit: Whether it is judged per claim or per paragraph.
        kind: "binary" (values no/yes) or "nominal".
        question: The question a rater answers.
        values: Allowed values, in display order.
        group: Optional group name (e.g. "overgeneralisation").
        yes_when: For binary codes, when to answer yes.
        no_when: For binary codes, when to answer no.
        references: Sources of the definition.
    """

    id: str
    unit: Unit
    kind: str
    question: str
    values: tuple[CodeValue, ...]
    group: str | None = None
    yes_when: str = ""
    no_when: str = ""
    references: tuple[str, ...] = ()

    @property
    def value_ids(self) -> tuple[str, ...]:
        """The allowed value identifiers, in display order."""
        return tuple(value.id for value in self.values)


@dataclass(frozen=True, slots=True)
class DerivedCode:
    """A code computed from rated codes.

    Attributes:
        id: Code identifier.
        unit: The unit of the codes it combines.
        rule: Combination rule; only "any_yes" is defined.
        of: The binary codes it combines.
        description: What it means.
    """

    id: str
    unit: Unit
    rule: str
    of: tuple[str, ...]
    description: str = ""


@dataclass(frozen=True, slots=True)
class Rubric:
    """A loaded rubric.

    Attributes:
        id: Rubric identifier, e.g. "rubric_v1".
        status: "DRAFT" until the owner approves it.
        codes: Rated codes, in file order.
        derived: Computed codes.
        units: Description of each unit.
        sha256: SHA-256 of the source file, recorded with every rating.
    """

    id: str
    status: str
    codes: tuple[RubricCode, ...]
    derived: tuple[DerivedCode, ...]
    units: Mapping[Unit, str]
    sha256: str

    def code(self, code_id: str) -> RubricCode:
        """Return a rated code by ID.

        Args:
            code_id: The code identifier.

        Returns:
            The code.

        Raises:
            KeyError: If no rated code has that ID.
        """
        for code in self.codes:
            if code.id == code_id:
                return code
        raise KeyError(code_id)

    def codes_for(self, unit: Unit) -> tuple[RubricCode, ...]:
        """Return the rated codes judged on one unit.

        Args:
            unit: Claim or paragraph.

        Returns:
            Codes in file order.
        """
        return tuple(code for code in self.codes if code.unit is unit)

    def validate_labels(self, unit: Unit, labels: Mapping[str, str]) -> list[str]:
        """Check one unit's labels against the rubric.

        Args:
            unit: The unit the labels describe.
            labels: Code ID to value ID.

        Returns:
            Error messages; empty when every code for the unit has exactly one
            allowed value and no unknown code is present.
        """
        errors: list[str] = []
        expected = {code.id: code for code in self.codes_for(unit)}
        for code_id in sorted(expected.keys() - labels.keys()):
            errors.append(f"missing code {code_id!r}")
        for code_id in sorted(labels.keys() - expected.keys()):
            errors.append(f"unknown code {code_id!r} for unit {unit.value!r}")
        for code_id, value in labels.items():
            code = expected.get(code_id)
            if code is not None and value not in code.value_ids:
                errors.append(f"code {code_id!r}: value {value!r} not in {list(code.value_ids)}")
        return errors

    def derive(self, unit: Unit, labels: Mapping[str, str]) -> dict[str, str]:
        """Compute the derived codes for one unit's (valid) labels.

        Args:
            unit: The unit the labels describe.
            labels: Code ID to value ID for the unit's rated codes.

        Returns:
            Derived code ID to "yes" or "no".
        """
        derived: dict[str, str] = {}
        for code in self.derived:
            if code.unit is unit:
                derived[code.id] = "yes" if any(labels.get(c) == "yes" for c in code.of) else "no"
        return derived


def load_rubric(path: Path | None = None) -> Rubric:
    """Load and validate a rubric YAML file.

    Args:
        path: The file; defaults to ``benchmark/rubric/rubric_v1.yaml``.

    Returns:
        The rubric.

    Raises:
        RubricError: If the file breaks any rule in :func:`parse_rubric`.
    """
    path = path or RUBRIC_DIR / "rubric_v1.yaml"
    return parse_rubric(path.read_text(encoding="utf-8"))


def parse_rubric(text: str) -> Rubric:
    """Parse and validate rubric YAML.

    Rules: unique code IDs; units are "claim" or "paragraph"; binary codes
    have no explicit values (they are always no/yes) and nominal codes list
    at least two unique values; derived codes combine existing binary codes
    of their own unit with the "any_yes" rule.

    Args:
        text: YAML text.

    Returns:
        The rubric.

    Raises:
        RubricError: If any rule is broken.
    """
    raw: Any = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise RubricError("rubric must be a mapping")
    for key in ("id", "status", "codes", "units"):
        if key not in raw:
            raise RubricError(f"rubric is missing {key!r}")

    units = {Unit(name): str(description) for name, description in raw["units"].items()}
    codes = tuple(_parse_code(item) for item in raw["codes"])
    ids = [code.id for code in codes]
    if len(ids) != len(set(ids)):
        raise RubricError(f"duplicate code IDs in {ids}")

    # Derived codes may only combine binary codes of the same unit.
    by_id = {code.id: code for code in codes}
    derived: list[DerivedCode] = []
    for item in raw.get("derived") or ():
        code = DerivedCode(
            id=str(item["id"]),
            unit=Unit(item["unit"]),
            rule=str(item["rule"]),
            of=tuple(str(c) for c in item["of"]),
            description=str(item.get("description", "")).strip(),
        )
        if code.rule != "any_yes":
            raise RubricError(f"derived code {code.id!r}: unknown rule {code.rule!r}")
        if code.id in by_id:
            raise RubricError(f"derived code {code.id!r} clashes with a rated code")
        for part in code.of:
            source = by_id.get(part)
            if source is None or source.kind != "binary" or source.unit is not code.unit:
                raise RubricError(
                    f"derived code {code.id!r}: {part!r} is not a binary {code.unit} code"
                )
        derived.append(code)

    return Rubric(
        id=str(raw["id"]),
        status=str(raw["status"]),
        codes=codes,
        derived=tuple(derived),
        units=units,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _parse_code(item: Any) -> RubricCode:
    """Parse one entry of the rubric's ``codes`` list.

    Args:
        item: The YAML mapping.

    Returns:
        The code.

    Raises:
        RubricError: If the entry is malformed.
    """
    if not isinstance(item, dict) or "id" not in item:
        raise RubricError(f"code entry must be a mapping with an id: {item!r}")
    code_id = str(item["id"])
    kind = item.get("kind")
    try:
        unit = Unit(str(item.get("unit")))
    except ValueError as exc:
        raise RubricError(f"code {code_id!r}: unit must be 'claim' or 'paragraph'") from exc
    if not item.get("question"):
        raise RubricError(f"code {code_id!r}: question is required")

    # Binary codes are always no/yes; nominal codes list their values.
    if kind == "binary":
        if "values" in item:
            raise RubricError(f"binary code {code_id!r} must not list values")
        values = tuple(CodeValue(value, value.capitalize()) for value in BINARY_VALUES)
    elif kind == "nominal":
        values = tuple(
            CodeValue(str(v["id"]), str(v["label"]), str(v.get("definition", "")).strip())
            for v in item.get("values") or ()
        )
        value_ids = [value.id for value in values]
        if len(values) < 2 or len(value_ids) != len(set(value_ids)):
            raise RubricError(f"nominal code {code_id!r} needs at least two unique values")
    else:
        raise RubricError(f"code {code_id!r}: kind must be 'binary' or 'nominal'")

    return RubricCode(
        id=code_id,
        unit=unit,
        kind=kind,
        question=" ".join(str(item["question"]).split()),
        values=values,
        group=item.get("group"),
        yes_when=" ".join(str(item.get("yes_when", "")).split()),
        no_when=" ".join(str(item.get("no_when", "")).split()),
        references=tuple(str(r) for r in item.get("references") or ()),
    )
