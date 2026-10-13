"""Merge several raters' labels into final labels, with adjudication.

Workflow (decisions.md §1.4: disagreements adjudicated and agreement
reported):

1. :func:`merge_labels` without adjudications gives a final value wherever the
   raters agree (or, under the "majority" policy, where a strict majority
   exists) and marks every other code "unresolved".
2. :func:`write_disagreements` exports the unresolved codes as a CSV with an
   empty ``adjudicated_value`` column for the adjudicator.
3. :func:`read_adjudications` reads the completed CSV back, and a second
   :func:`merge_labels` call applies it. An adjudicated value always wins,
   including over agreement, so an adjudicator can correct a shared mistake.

Nothing is guessed: a code with no agreement and no adjudication stays
unresolved and is reported as such.
"""

from __future__ import annotations

import csv
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from rbbench.agreement.report import labels_by_unit
from rbbench.ratings import Rating
from rbbench.rubric import Rubric, Unit

DISAGREEMENT_COLUMNS = (
    "unit",
    "unit_id",
    "code_id",
    "rater_values",
    "allowed_values",
    "adjudicated_value",
    "adjudicator",
    "note",
)


class AdjudicationError(ValueError):
    """Raised when an adjudication file is malformed or names an invalid value."""


class Policy(StrEnum):
    """How agreement turns into a final label before adjudication."""

    UNANIMOUS = "unanimous"
    MAJORITY = "majority"


class Basis(StrEnum):
    """Why a final label has its value."""

    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    ADJUDICATED = "adjudicated"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class FinalLabel:
    """The merged label of one rated code on one unit.

    Attributes:
        unit: Claim or paragraph.
        unit_id: The unit.
        code_id: The rated code (derived codes are recomputed from finals).
        value: The final value, or None when unresolved.
        basis: How the value was reached.
        rater_values: Each rater's value.
    """

    unit: Unit
    unit_id: str
    code_id: str
    value: str | None
    basis: Basis
    rater_values: Mapping[str, str]

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict of every field.
        """
        return {
            "unit": self.unit.value,
            "unit_id": self.unit_id,
            "code_id": self.code_id,
            "value": self.value,
            "basis": self.basis.value,
            "rater_values": dict(self.rater_values),
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> FinalLabel:
        """Build a final label from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The final label.
        """
        value = record["value"]
        return cls(
            unit=Unit(record["unit"]),
            unit_id=str(record["unit_id"]),
            code_id=str(record["code_id"]),
            value=None if value is None else str(value),
            basis=Basis(record["basis"]),
            rater_values={str(k): str(v) for k, v in record["rater_values"].items()},
        )


AdjudicationKey = tuple[str, str, str]


def merge_labels(
    ratings: Sequence[Rating],
    rubric: Rubric,
    *,
    adjudications: Mapping[AdjudicationKey, str] | None = None,
    policy: Policy = Policy.UNANIMOUS,
) -> list[FinalLabel]:
    """Merge ratings into one final label per (unit, rated code).

    Args:
        ratings: Ratings from one or more raters.
        rubric: The rubric they follow.
        adjudications: ``(unit, unit_id, code_id)`` -> adjudicated value.
        policy: Unanimous (default) or strict majority before adjudication.

    Returns:
        Final labels sorted by unit, unit ID and rubric code order.

    Raises:
        AdjudicationError: If an adjudicated value is not allowed for its code.
    """
    adjudications = adjudications or {}
    finals: list[FinalLabel] = []
    for unit in Unit:
        index = labels_by_unit(ratings, rubric, unit)
        for unit_id in sorted(index):
            by_rater = index[unit_id]
            for code in rubric.codes_for(unit):
                values = {r: labels[code.id] for r, labels in by_rater.items() if code.id in labels}
                key = (unit.value, unit_id, code.id)
                # An adjudicated value always wins; it must be a value the code allows.
                if key in adjudications:
                    value = adjudications[key]
                    if value not in code.value_ids:
                        raise AdjudicationError(f"{key}: {value!r} not in {list(code.value_ids)}")
                    finals.append(
                        FinalLabel(unit, unit_id, code.id, value, Basis.ADJUDICATED, values)
                    )
                    continue
                finals.append(_merge_one(unit, unit_id, code.id, values, policy))
    return finals


def _merge_one(
    unit: Unit, unit_id: str, code_id: str, values: Mapping[str, str], policy: Policy
) -> FinalLabel:
    """Merge one code's rater values without adjudication.

    Args:
        unit: The unit type.
        unit_id: The unit.
        code_id: The code.
        values: Rater ID -> value.
        policy: Unanimous or majority.

    Returns:
        The final label; unresolved when there are fewer than two raters or no
        agreement under the policy.
    """
    counts = Counter(values.values())
    if len(values) >= 2 and len(counts) == 1:
        return FinalLabel(unit, unit_id, code_id, next(iter(counts)), Basis.UNANIMOUS, values)
    if policy is Policy.MAJORITY and len(values) >= 3:
        (top, top_count), *rest = counts.most_common()
        # A strict majority: more than half of the raters, never a tie.
        if top_count * 2 > len(values) and (not rest or rest[0][1] < top_count):
            return FinalLabel(unit, unit_id, code_id, top, Basis.MAJORITY, values)
    return FinalLabel(unit, unit_id, code_id, None, Basis.UNRESOLVED, values)


def write_disagreements(path: Path, finals: Sequence[FinalLabel], rubric: Rubric) -> int:
    """Export unresolved labels as a CSV for the adjudicator.

    Args:
        path: Destination CSV.
        finals: Output of :func:`merge_labels`.
        rubric: The rubric, for the allowed values column.

    Returns:
        The number of rows written.
    """
    rows = [final for final in finals if final.basis is Basis.UNRESOLVED]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DISAGREEMENT_COLUMNS)
        writer.writeheader()
        for final in rows:
            writer.writerow(
                {
                    "unit": final.unit.value,
                    "unit_id": final.unit_id,
                    "code_id": final.code_id,
                    "rater_values": "; ".join(
                        f"{rater}={value}" for rater, value in sorted(final.rater_values.items())
                    ),
                    "allowed_values": "|".join(rubric.code(final.code_id).value_ids),
                    "adjudicated_value": "",
                    "adjudicator": "",
                    "note": "",
                }
            )
    return len(rows)


def read_adjudications(path: Path) -> dict[AdjudicationKey, str]:
    """Read a completed disagreement CSV; rows left blank are skipped.

    Args:
        path: CSV written by :func:`write_disagreements` and filled in.

    Returns:
        ``(unit, unit_id, code_id)`` -> adjudicated value.

    Raises:
        AdjudicationError: If required columns are missing, a filled row has no
            adjudicator, or a key appears twice.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = {"unit", "unit_id", "code_id", "adjudicated_value", "adjudicator"} - set(
            reader.fieldnames or ()
        )
        if missing:
            raise AdjudicationError(f"{path}: missing columns {sorted(missing)}")
        result: dict[AdjudicationKey, str] = {}
        for line, row in enumerate(reader, start=2):
            value = (row["adjudicated_value"] or "").strip()
            if not value:
                continue
            # Every decision must be attributable to a named adjudicator.
            if not (row["adjudicator"] or "").strip():
                raise AdjudicationError(f"{path}:{line}: adjudicated value without adjudicator")
            key = (row["unit"].strip(), row["unit_id"].strip(), row["code_id"].strip())
            if key in result:
                raise AdjudicationError(f"{path}:{line}: duplicate adjudication for {key}")
            result[key] = value
    return result


def final_labels_by_unit(
    finals: Sequence[FinalLabel], rubric: Rubric
) -> dict[tuple[Unit, str], dict[str, str | None]]:
    """Group final labels per unit and add derived codes where computable.

    A derived code is "yes" if any resolved component is "yes", "no" if every
    component is resolved "no", and None (unresolved) otherwise.

    Args:
        finals: Output of :func:`merge_labels`.
        rubric: The rubric.

    Returns:
        ``(unit, unit_id)`` -> code ID -> final value (None if unresolved).
    """
    grouped: dict[tuple[Unit, str], dict[str, str | None]] = {}
    for final in finals:
        grouped.setdefault((final.unit, final.unit_id), {})[final.code_id] = final.value
    for (unit, _), labels in grouped.items():
        for derived in rubric.derived:
            if derived.unit is not unit:
                continue
            parts = [labels.get(code_id) for code_id in derived.of]
            if any(part == "yes" for part in parts):
                labels[derived.id] = "yes"
            elif all(part == "no" for part in parts):
                labels[derived.id] = "no"
            else:
                labels[derived.id] = None
    return grouped


def finals_as_ratings(
    finals: Sequence[FinalLabel], rubric: Rubric, *, rater_id: str = "adjudicated"
) -> list[Rating]:
    """Turn resolved final labels into one pseudo-rater's ratings.

    Used to measure the LLM judge against the adjudicated human labels with
    the same agreement statistics. Unresolved codes are left out of the
    labels, so they count as missing rather than as a value.

    Args:
        finals: Output of :func:`merge_labels`.
        rubric: The rubric.
        rater_id: The pseudo-rater's ID.

    Returns:
        One rating per unit with at least one resolved code.
    """
    grouped: dict[tuple[Unit, str], dict[str, str]] = {}
    for final in finals:
        labels = grouped.setdefault((final.unit, final.unit_id), {})
        if final.value is not None:
            labels[final.code_id] = final.value
    return [
        Rating(
            rater_id=rater_id,
            unit=unit,
            unit_id=unit_id,
            labels=labels,
            rubric_id=rubric.id,
            rubric_sha256=rubric.sha256,
        )
        for (unit, unit_id), labels in grouped.items()
        if labels
    ]
