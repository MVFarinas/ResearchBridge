"""SYNTHETIC rater exports for the dry run and tests. Never real ratings.

A synthetic rater answers every code of every unit in a packet. A "base"
answer per (unit, code) is drawn from a seeded generator, mostly the clean
value (the first allowed value); each synthetic rater then copies the base
and changes a configurable share of answers at random. The result has
realistic shape (skewed codes, partial agreement) so the agreement and
adjudication code can be exercised end to end, and nothing about it says
anything about real rewrites.
"""

from __future__ import annotations

import random
from typing import Any

from rbbench.packets.importer import RATINGS_FORMAT

SYNTHETIC_COMMENT = "SYNTHETIC rating generated for a dry run"


def synthetic_export(
    packet: dict[str, Any], *, base_seed: str, rater_seed: str, change_rate: float
) -> dict[str, Any]:
    """Build a complete SYNTHETIC ratings export for one packet.

    Args:
        packet: A rater packet (``<rater>.packet.json``).
        base_seed: Seed shared by all synthetic raters (the common answers).
        rater_seed: Seed for this rater's deviations.
        change_rate: Share of answers this rater changes from the base.

    Returns:
        A ratings export in the importer's format, marked synthetic.
    """
    codes = packet["rubric"]["codes"]
    deviate = random.Random(rater_seed)  # noqa: S311 - synthetic test data, not security
    ratings = []
    for item in packet["items"]:
        for paragraph in item["paragraphs"]:
            units = [("claim", c["unit_id"]) for c in paragraph["claims"]]
            units.append(("paragraph", paragraph["unit_id"]))
            for unit, unit_id in units:
                labels = {}
                for code in (c for c in codes if c["unit"] == unit):
                    values = [v["id"] for v in code["values"]]
                    # The shared base answer: clean 85% of the time.
                    base = random.Random(f"{base_seed}:{unit_id}:{code['id']}")  # noqa: S311
                    answer = values[0] if base.random() < 0.85 else base.choice(values[1:])
                    if deviate.random() < change_rate:
                        answer = deviate.choice(values)
                    labels[code["id"]] = answer
                ratings.append(
                    {
                        "unit": unit,
                        "unit_id": unit_id,
                        "labels": labels,
                        "comment": SYNTHETIC_COMMENT,
                    }
                )
    return {
        "format": RATINGS_FORMAT,
        "packet_id": packet["packet_id"],
        "rater_id": packet["rater_id"],
        "rubric_id": packet["rubric"]["id"],
        "rubric_sha256": packet["rubric"]["sha256"],
        "synthetic": True,
        "exported_at": "synthetic",
        "complete": True,
        "ratings": ratings,
    }
