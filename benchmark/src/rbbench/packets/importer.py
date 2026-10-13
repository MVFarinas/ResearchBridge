"""Import completed ratings exported from rater packets.

Checks, all of which must pass before anything is written:

* the export's format, packet ID, rater ID and rubric hash match the packet
  key (a rater ID not in the key is refused);
* every rated unit is in the key, at most once, with labels the rubric allows
  for that unit type;
* the export is complete (every unit rated with every code), unless the
  caller explicitly accepts partial exports.

Opaque unit IDs are mapped back to real claim and paragraph IDs through the
key, so the resulting :class:`rbbench.ratings.Rating` records can be merged
with other raters' and the judge's.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rbbench.packets.build import KEY_FORMAT
from rbbench.ratings import Rating
from rbbench.rubric import Rubric, Unit

RATINGS_FORMAT = "rbbench-ratings/1"


class RatingsImportError(ValueError):
    """Raised when a ratings export does not match its packet or the rubric."""


def load_key(path: Path) -> dict[str, Any]:
    """Load and sanity-check a packet key.

    Args:
        path: ``key.json`` written by :func:`rbbench.packets.build.build_packets`.

    Returns:
        The key document.

    Raises:
        RatingsImportError: If it is not a packet key.
    """
    key: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(key, dict) or key.get("format") != KEY_FORMAT:
        raise RatingsImportError(f"{path} is not a packet key")
    return key


def import_ratings(
    export_path: Path, key: dict[str, Any], rubric: Rubric, *, allow_incomplete: bool = False
) -> list[Rating]:
    """Validate one rater's export and convert it to ratings.

    Args:
        export_path: The ``<rater>.ratings.json`` file.
        key: The packet key.
        rubric: The rubric (its hash must match the packet's).
        allow_incomplete: Accept units with missing codes or missing units
            (incomplete units are skipped, never padded).

    Returns:
        Ratings with real unit IDs, in the key's order.

    Raises:
        RatingsImportError: On any mismatch, unknown unit, duplicate, invalid label,
            or (unless allowed) incompleteness.
    """
    export: Any = json.loads(export_path.read_text(encoding="utf-8"))
    if not isinstance(export, dict) or export.get("format") != RATINGS_FORMAT:
        raise RatingsImportError(f"{export_path}: not a ratings export")

    # The export must belong to this packet, a known rater and this exact rubric.
    rater_id = str(export.get("rater_id", ""))
    if export.get("packet_id") != key["packet_id"]:
        raise RatingsImportError(
            f"{export_path}: packet {export.get('packet_id')!r} is not {key['packet_id']!r}"
        )
    if rater_id not in key["raters"]:
        raise RatingsImportError(f"{export_path}: rater {rater_id!r} is not in the packet key")
    if export.get("rubric_sha256") != rubric.sha256 or key["rubric_sha256"] != rubric.sha256:
        raise RatingsImportError(f"{export_path}: rated with a different rubric version")

    units: dict[str, dict[str, str]] = key["units"]
    ratings: dict[str, Rating] = {}
    for entry in export.get("ratings", []):
        opaque = str(entry.get("unit_id", ""))
        if opaque not in units:
            raise RatingsImportError(f"{export_path}: unknown unit {opaque!r}")
        if opaque in ratings:
            raise RatingsImportError(f"{export_path}: unit {opaque!r} rated twice")
        unit = Unit(units[opaque]["unit"])
        labels = {str(k): str(v) for k, v in (entry.get("labels") or {}).items()}
        problems = rubric.validate_labels(unit, labels)
        # Missing codes make a unit incomplete; anything else is an error.
        if any(not p.startswith("missing code") for p in problems):
            raise RatingsImportError(f"{export_path}: unit {opaque!r}: {'; '.join(problems)}")
        if problems:
            continue
        ratings[opaque] = Rating(
            rater_id=rater_id,
            unit=unit,
            unit_id=units[opaque]["unit_id"],
            labels=labels,
            rubric_id=rubric.id,
            rubric_sha256=rubric.sha256,
            packet_id=key["packet_id"],
            comment=str(entry.get("comment", "")),
            synthetic=bool(key.get("synthetic", False)),
        )

    missing = [opaque for opaque in units if opaque not in ratings]
    if missing and not allow_incomplete:
        raise RatingsImportError(
            f"{export_path}: {len(missing)} of {len(units)} units are unrated or incomplete"
        )
    return [ratings[opaque] for opaque in units if opaque in ratings]
