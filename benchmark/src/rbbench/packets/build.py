"""Per-rater packets that need no server: a self-contained HTML form plus its JSON.

For each rater the builder writes:

* ``<rater>.html``: open in any browser, offline. A Content-Security-Policy
  forbids every network request, all text is inserted as text (never HTML),
  answers autosave in the browser, and an export button downloads
  ``<rater>.ratings.json``.
* ``<rater>.packet.json``: the same data, for tooling or a rater who prefers it.

and once per packet:

* ``key.json``: the unblinding key, **kept by the coordinator, never sent**.
  Raters see opaque unit IDs and anonymous "Rewrite n" labels, never the arm,
  model or rewrite ID; the key maps opaque IDs back to claim and paragraph
  unit IDs for the importer.

Each rater gets the rewrites in a different seeded order, to spread order
effects across raters.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from rbbench.claims import Claim, paragraph_unit_id
from rbbench.jsonl import utc_now_iso, write_json, write_text_atomic
from rbbench.rewrite.harness import RewriteRecord
from rbbench.rubric import Rubric

PACKET_FORMAT = "rbbench-packet/1"
KEY_FORMAT = "rbbench-packet-key/1"
SYNTHETIC_BANNER = (
    "SYNTHETIC DRY RUN: this packet was built from fake (synthetic) rewrites and claims. "
    "It is for testing the tools only. Do not rate it as real data."
)


class PacketError(ValueError):
    """Raised when packets cannot be built from the given inputs."""


@dataclass(frozen=True, slots=True)
class PacketPaths:
    """Where one rater's packet files were written.

    Attributes:
        rater_id: The rater.
        html: The HTML form.
        packet_json: The packet data as JSON.
    """

    rater_id: str
    html: Path
    packet_json: Path


def opaque_id(packet_id: str, unit_id: str, prefix: str) -> str:
    """Return a stable opaque ID that hides arm, model and rewrite from raters.

    Args:
        packet_id: The packet.
        unit_id: The real claim or paragraph unit ID.
        prefix: "c" for claims, "p" for paragraphs.

    Returns:
        ``<prefix>-<12 hex characters>``.
    """
    digest = hashlib.sha256(f"{packet_id}\x00{unit_id}".encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


def rubric_for_packet(rubric: Rubric) -> dict[str, Any]:
    """Return the rubric fields the form needs.

    Args:
        rubric: The rubric.

    Returns:
        A JSON-serialisable rubric summary.
    """
    codes = []
    for code in rubric.codes:
        help_text = " ".join(
            part
            for part in (
                f"Yes when: {code.yes_when}" if code.yes_when else "",
                f"No when: {code.no_when}" if code.no_when else "",
            )
            if part
        )
        codes.append(
            {
                "id": code.id,
                "unit": code.unit.value,
                "question": code.question,
                "help": help_text,
                "values": [
                    {"id": v.id, "label": v.label, "definition": v.definition} for v in code.values
                ],
            }
        )
    return {"id": rubric.id, "sha256": rubric.sha256, "status": rubric.status, "codes": codes}


def build_packets(
    rewrites: Sequence[RewriteRecord],
    claims: Sequence[Claim],
    rubric: Rubric,
    rater_ids: Sequence[str],
    out_dir: Path,
    *,
    packet_id: str,
    titles: dict[str, str] | None = None,
    attributions: dict[str, str] | None = None,
    seed: str = "rbbench-packets-v1",
) -> list[PacketPaths]:
    """Write one packet per rater plus the packet key.

    Args:
        rewrites: Valid rewrites to rate.
        claims: Their claims.
        rubric: The rubric.
        rater_ids: Pseudonymous rater IDs (unique).
        out_dir: Output directory (gitignored data).
        packet_id: Identifier for this packet set.
        titles: Paper titles by paper key.
        attributions: Attribution line by paper key (licence and source).
        seed: Seed for the per-rater item order.

    Returns:
        The paths written per rater.

    Raises:
        PacketError: If there is nothing to rate, a rewrite is invalid, rater
            IDs repeat, or a rewrite has no claims.
    """
    if not rewrites or not rater_ids or len(set(rater_ids)) != len(rater_ids):
        raise PacketError("need at least one rewrite and unique rater IDs")
    if any(not r.valid for r in rewrites):
        raise PacketError("only valid rewrites can be rated")
    synthetic = any(r.synthetic for r in rewrites) or any(c.synthetic for c in claims)
    items, key = _items_and_key(rewrites, claims, packet_id, titles or {}, attributions or {})

    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        out_dir / "key.json",
        {
            "format": KEY_FORMAT,
            "packet_id": packet_id,
            "rubric_id": rubric.id,
            "rubric_sha256": rubric.sha256,
            "synthetic": synthetic,
            "raters": list(rater_ids),
            "units": key,
            "note": "Unblinding key: keep it; never send it to raters.",
        },
    )

    template = resources.files("rbbench.packets").joinpath("template.html").read_text("utf-8")
    written: list[PacketPaths] = []
    for rater_id in rater_ids:
        # A different, reproducible order of rewrites for each rater.
        order = list(items)
        random.Random(f"{seed}:{packet_id}:{rater_id}").shuffle(order)  # noqa: S311
        packet = {
            "format": PACKET_FORMAT,
            "packet_id": packet_id,
            "rater_id": rater_id,
            "created": utc_now_iso(),
            "synthetic": synthetic,
            "banner": SYNTHETIC_BANNER if synthetic else "",
            "rubric": rubric_for_packet(rubric),
            "items": order,
        }
        paths = PacketPaths(
            rater_id, out_dir / f"{rater_id}.html", out_dir / f"{rater_id}.packet.json"
        )
        write_json(paths.packet_json, packet)
        write_text_atomic(paths.html, template.replace("__PACKET_JSON__", embed_json(packet)))
        written.append(paths)
    return written


def embed_json(data: Any) -> str:
    """Serialise JSON for a ``<script type="application/json">`` element.

    ``<``, ``>`` and ``&`` are escaped as JSON unicode escapes, so no text
    in the data (for example ``</script>`` in a paper) can end the element.

    Args:
        data: JSON-serialisable data.

    Returns:
        Safe JSON text.
    """
    text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _items_and_key(
    rewrites: Sequence[RewriteRecord],
    claims: Sequence[Claim],
    packet_id: str,
    titles: dict[str, str],
    attributions: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    """Build the blinded items and the opaque-ID key.

    Args:
        rewrites: The rewrites.
        claims: Their claims.
        packet_id: The packet.
        titles: Paper titles.
        attributions: Attribution lines.

    Returns:
        ``(items, key)``: items in rewrite order; key maps opaque ID to the
        real unit, rewrite, arm and model.

    Raises:
        PacketError: If a rewrite has no claims.
    """
    by_paragraph: dict[tuple[str, str], list[Claim]] = {}
    for claim in claims:
        by_paragraph.setdefault((claim.rewrite_id, claim.paragraph_id), []).append(claim)

    items: list[dict[str, Any]] = []
    key: dict[str, dict[str, str]] = {}
    for rewrite in rewrites:
        sources = dict(rewrite.source)
        paragraphs = []
        for paragraph in rewrite.paragraphs:
            paragraph_claims = by_paragraph.get((rewrite.rewrite_id, paragraph.paragraph_id), [])
            if not paragraph_claims:
                raise PacketError(f"{rewrite.rewrite_id}#{paragraph.paragraph_id} has no claims")
            real_paragraph = paragraph_unit_id(rewrite.rewrite_id, paragraph.paragraph_id)
            paragraph_opaque = opaque_id(packet_id, real_paragraph, "p")
            key[paragraph_opaque] = _key_entry("paragraph", real_paragraph, rewrite)
            claim_entries = []
            for claim in paragraph_claims:
                claim_opaque = opaque_id(packet_id, claim.claim_id, "c")
                key[claim_opaque] = _key_entry("claim", claim.claim_id, rewrite)
                claim_entries.append(
                    {"unit_id": claim_opaque, "text": claim.text, "in_addition": claim.in_addition}
                )
            paragraphs.append(
                {
                    "unit_id": paragraph_opaque,
                    "source_text": sources[paragraph.paragraph_id],
                    "rewritten_text": paragraph.text,
                    "additions": [{"start": a.start, "end": a.end} for a in paragraph.additions],
                    "claims": claim_entries,
                }
            )
        items.append(
            {
                "paper_title": titles.get(rewrite.paper_key, rewrite.paper_key),
                "attribution": attributions.get(rewrite.paper_key, ""),
                "source_passage": [{"text": text} for _, text in rewrite.source],
                "paragraphs": paragraphs,
            }
        )
    return items, key


def _key_entry(unit: str, unit_id: str, rewrite: RewriteRecord) -> dict[str, str]:
    """Return one unblinding-key entry.

    Args:
        unit: "claim" or "paragraph".
        unit_id: The real unit ID.
        rewrite: The rewrite it belongs to.

    Returns:
        The entry.
    """
    return {
        "unit": unit,
        "unit_id": unit_id,
        "rewrite_id": rewrite.rewrite_id,
        "arm": rewrite.arm,
        "model": rewrite.model,
    }
