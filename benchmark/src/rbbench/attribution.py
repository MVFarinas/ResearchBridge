"""Attribution lines for source text shown to raters (CC BY and the PMC bucket terms).

Rater packets reproduce source paragraphs verbatim, which is redistribution:
CC BY requires attribution (title, source, licence), and the PMC Cloud
Service terms ask users to acknowledge NLM without implying endorsement. One
line per paper is built here from its ingest record, so the CLI and the dry
run attribute identically.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from rbcore.licences import LicenceField

NLM_ACKNOWLEDGEMENT = (
    "Full text from the PMC Open Access Subset, courtesy of the U.S. National Library of "
    "Medicine (NLM); no endorsement by NLM is implied."
)


class AttributionError(ValueError):
    """Raised when a paper record lacks what an attribution needs."""


def attribution_line(paper: Mapping[str, Any]) -> str:
    """Build the attribution for one paper from its ``papers.jsonl`` record.

    Args:
        paper: A record written by :meth:`rbbench.ingest.IngestedPaper.to_record`.

    Returns:
        "<title>. <journal>. https://doi.org/<doi>. Licence: <licence>. Source:
        <url>." followed by the NLM acknowledgement when the licence evidence
        came from the PMC Cloud Service.

    Raises:
        AttributionError: If the record has no title or no licence label.
    """
    title = str(paper.get("title") or "").strip()
    licence = str(paper.get("licence") or "").strip()
    if not title or not licence:
        raise AttributionError(f"paper {paper.get('paper_key')!r} has no title or licence")
    metadata: Mapping[str, Any] = paper.get("metadata") or {}

    # Title, journal and DOI identify the work; the licence is a CC BY condition.
    parts = [title.rstrip(".") + "."]
    if paper.get("journal"):
        parts.append(f"{paper['journal']}.")
    if paper.get("doi"):
        parts.append(f"https://doi.org/{paper['doi']}.")
    parts.append(f"Licence: {licence}.")
    if metadata.get("source_url"):
        parts.append(f"Source: {metadata['source_url']}.")

    # Text taken from the PMC bucket carries the NLM acknowledgement its terms ask for.
    from_pmc = any(
        e.get("field") == LicenceField.PMC_LICENSE_CODE.value for e in paper.get("evidence", [])
    )
    if from_pmc:
        parts.append(NLM_ACKNOWLEDGEMENT)
    return " ".join(parts)
