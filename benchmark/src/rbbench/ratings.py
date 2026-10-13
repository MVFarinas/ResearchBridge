"""The normalised rating record shared by raters, the importer, agreement and the judge.

One :class:`Rating` is one rater's labels for one unit (a claim or a
paragraph). Human ratings come in through the packet importer; the LLM judge
produces the same shape with ``rater_id`` naming the judge, so judge-vs-human
agreement reuses the same statistics.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rbbench.jsonl import read_jsonl, write_jsonl
from rbbench.rubric import Unit


@dataclass(frozen=True, slots=True)
class Rating:
    """One rater's labels for one unit.

    Attributes:
        rater_id: Who rated (a pseudonymous rater ID, or a judge ID).
        unit: Claim or paragraph.
        unit_id: The claim ID or paragraph-alignment ID.
        labels: Code ID to value ID, for the rubric's codes on this unit.
        rubric_id: The rubric version used.
        rubric_sha256: SHA-256 of the rubric file used.
        packet_id: The packet the rating came from (empty for judge output).
        comment: The rater's free-text note, if any.
        synthetic: True for test or dry-run data, never real ratings.
    """

    rater_id: str
    unit: Unit
    unit_id: str
    labels: Mapping[str, str]
    rubric_id: str
    rubric_sha256: str
    packet_id: str = ""
    comment: str = ""
    synthetic: bool = field(default=False)

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with ``record_type`` "rating".
        """
        return {
            "record_type": "rating",
            "rater_id": self.rater_id,
            "unit": self.unit.value,
            "unit_id": self.unit_id,
            "labels": dict(self.labels),
            "rubric_id": self.rubric_id,
            "rubric_sha256": self.rubric_sha256,
            "packet_id": self.packet_id,
            "comment": self.comment,
            "synthetic": self.synthetic,
        }

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> Rating:
        """Build a rating from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The rating.

        Raises:
            KeyError: If a required field is missing.
            ValueError: If the unit is unknown.
        """
        return cls(
            rater_id=str(record["rater_id"]),
            unit=Unit(record["unit"]),
            unit_id=str(record["unit_id"]),
            labels={str(k): str(v) for k, v in record["labels"].items()},
            rubric_id=str(record["rubric_id"]),
            rubric_sha256=str(record["rubric_sha256"]),
            packet_id=str(record.get("packet_id", "")),
            comment=str(record.get("comment", "")),
            synthetic=bool(record.get("synthetic", False)),
        )


def save_ratings(path: Path, ratings: Iterable[Rating]) -> int:
    """Write ratings as JSON Lines.

    Args:
        path: Destination file.
        ratings: The ratings.

    Returns:
        How many were written.
    """
    return write_jsonl(path, (rating.to_record() for rating in ratings))


def load_ratings(path: Path) -> list[Rating]:
    """Read ratings written by :func:`save_ratings`.

    Args:
        path: The JSON Lines file.

    Returns:
        The ratings, in file order.
    """
    return [Rating.from_record(record) for record in read_jsonl(path)]
