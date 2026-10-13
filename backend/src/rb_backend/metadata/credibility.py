"""Paper-level, neutral credibility signals (decisions.md §2.3; journal-level signals deferred).

For one corpus paper this gathers, each with its source and "as of" date:

* **OpenAlex** (CC0): citation count, citations per year, field-weighted
  citation impact (FWCI) and citation percentile where computed, and the
  retraction flag.
* **NIH iCite** (public domain), for papers with a PMID: citations per year
  and the Relative Citation Ratio.
* **Crossref** (open metadata, including Retraction Watch data): retraction,
  expression-of-concern and correction notices.

Nothing here rates a journal or a publisher. Any source may be unavailable;
each section then says so, and cached answers are served stale (with their
original date) rather than dropped. A retraction reported by Crossref or
OpenAlex is also recorded on the paper, which stops it being rewritten.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.utils import timezone

from rb_backend.corpus.models import Paper
from rb_backend.corpus.retractions import (
    RETRACTION_SOURCE_CROSSREF_PUBLISHER,
    RETRACTION_SOURCE_CROSSREF_RW,
    RETRACTION_SOURCE_OPENALEX,
    record_external_retraction,
)
from rb_backend.metadata.cache import CacheResult
from rb_backend.metadata.crossref import EditorialNotice, parse_notices
from rb_backend.metadata.errors import UpstreamError
from rb_backend.metadata.icite import parse_pub
from rb_backend.metadata.openalex import CitationMetrics, parse_metrics
from rb_backend.metadata.services import MetadataClients, crossref_work, icite_pub, openalex_work

OPENALEX_ATTRIBUTION = {
    "name": "OpenAlex",
    "licence": "CC0",
    "url": "https://openalex.org/",
}
ICITE_ATTRIBUTION = {
    "name": "NIH iCite",
    "licence": "Public domain",
    "url": "https://icite.od.nih.gov/",
}
CROSSREF_ATTRIBUTION = {
    "name": "Crossref, including the Retraction Watch Database",
    "licence": "Open metadata",
    "url": "https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/",
    "citation": (
        "Retraction Watch Database, The Center for Scientific Integrity; "
        "distributed by Crossref (https://doi.org/10.13003/c23rw1d9)."
    ),
}


def paper_credibility(
    paper: Paper, clients: MetadataClients, *, now: datetime | None = None
) -> dict[str, Any]:
    """Gather the credibility signals of one paper.

    Args:
        paper: A displayable corpus paper.
        clients: The metadata clients.
        now: Current time.

    Returns:
        A JSON-ready dict with ``openalex``, ``icite``, ``crossref`` and
        ``integrity`` sections.
    """
    now = now or timezone.now()

    doi, pmid = paper.doi, paper.pmid

    # OpenAlex by DOI, else PMID (it has no PMC ID lookup).
    def get_openalex() -> CacheResult | None:
        """Look the paper up in OpenAlex by its best identifier."""
        if doi:
            return openalex_work(clients, "doi", doi, now=now)
        return openalex_work(clients, "pmid", pmid, now=now) if pmid else None

    openalex = _section(get_openalex, OPENALEX_ATTRIBUTION)
    openalex_payload = openalex.pop("payload")
    metrics = parse_metrics(openalex_payload) if openalex["status"] == "ok" else None
    openalex["metrics"] = _metrics_dict(metrics) if metrics else None

    # iCite only covers PubMed-indexed papers.
    icite = _section(lambda: icite_pub(clients, pmid, now=now) if pmid else None, ICITE_ATTRIBUTION)
    icite_payload = icite.pop("payload")
    icite["metrics"] = _icite_dict(icite_payload) if icite["status"] == "ok" else None

    # Crossref notices need a DOI.
    crossref = _section(
        lambda: crossref_work(clients, doi, now=now) if doi else None, CROSSREF_ATTRIBUTION
    )
    crossref_payload = crossref.pop("payload")
    notices = parse_notices(crossref_payload) if crossref["status"] == "ok" else []
    crossref["notices"] = [_notice_dict(n) for n in notices]

    # Retractions from either source are recorded, so the paper is never rewritten.
    _record_retractions(paper, notices, metrics.is_retracted if metrics else False, now)
    return {
        "openalex": openalex,
        "icite": icite,
        "crossref": crossref,
        "integrity": _integrity(paper, notices),
    }


def _section(get: Callable[[], CacheResult | None], attribution: dict[str, str]) -> dict[str, Any]:
    """Run one cached lookup and describe its outcome.

    Args:
        get: A callable returning a :class:`CacheResult`, or None when the
            paper lacks the identifier the source needs.
        attribution: The source's name, licence and URL.

    Returns:
        ``{"status", "as_of", "stale", "message", "source", "payload"}``,
        where status is ok, not_found, not_applicable or unavailable.
    """
    try:
        result: CacheResult | None = get()
    except UpstreamError as exc:
        return {
            "status": "unavailable",
            "as_of": None,
            "stale": False,
            "message": f"{attribution['name']} could not be reached ({exc.status or 'error'}).",
            "source": attribution,
            "payload": None,
        }
    if result is None:
        return {
            "status": "not_applicable",
            "as_of": None,
            "stale": False,
            "message": f"{attribution['name']} needs an identifier this paper does not have.",
            "source": attribution,
            "payload": None,
        }
    # A cached "not found" is an answer too, with its own date.
    found = result.payload is not None
    if not found:
        message = f"{attribution['name']} has no record of this paper."
    elif result.stale:
        message = "Showing the last answer received; a refresh failed."
    else:
        message = ""
    return {
        "status": "ok" if found else "not_found",
        "as_of": result.as_of.isoformat(),
        "stale": result.stale,
        "message": message,
        "source": attribution,
        "payload": result.payload,
    }


def _metrics_dict(metrics: CitationMetrics) -> dict[str, Any]:
    """Serialise OpenAlex citation metrics.

    Args:
        metrics: The metrics.

    Returns:
        A JSON-ready dict.
    """
    return {
        "cited_by_count": metrics.cited_by_count,
        "counts_by_year": metrics.counts_by_year,
        "fwci": metrics.fwci,
        "citation_percentile": metrics.citation_percentile,
        "top_1_percent": metrics.top_1_percent,
        "top_10_percent": metrics.top_10_percent,
        "is_retracted": metrics.is_retracted,
    }


def _icite_dict(payload: object) -> dict[str, Any]:
    """Serialise an iCite record.

    Args:
        payload: A trimmed iCite record.

    Returns:
        A JSON-ready dict.
    """
    metrics = parse_pub(payload)
    return {
        "citation_count": metrics.citation_count,
        "citations_by_year": metrics.citations_by_year,
        "relative_citation_ratio": metrics.relative_citation_ratio,
        "rcr_provisional": metrics.rcr_provisional,
        "nih_percentile": metrics.nih_percentile,
        "is_research_article": metrics.is_research_article,
    }


def _notice_dict(notice: EditorialNotice) -> dict[str, Any]:
    """Serialise a Crossref notice.

    Args:
        notice: The notice.

    Returns:
        A JSON-ready dict with a DOI link to the notice when it has one.
    """
    return {
        "kind": notice.kind,
        "label": notice.label,
        "source": notice.source,
        "notice_doi": notice.notice_doi,
        "notice_url": f"https://doi.org/{notice.notice_doi}" if notice.notice_doi else None,
        "date": notice.notice_date.isoformat() if notice.notice_date else None,
        "retraction_watch_record": notice.record_id,
    }


def _record_retractions(
    paper: Paper, notices: list[EditorialNotice], openalex_retracted: bool, now: datetime
) -> None:
    """Record a retraction reported by Crossref or OpenAlex on the paper.

    Args:
        paper: The paper.
        notices: Crossref notices.
        openalex_retracted: OpenAlex's flag.
        now: Current time.
    """
    retraction = next((n for n in notices if n.is_retraction), None)
    if retraction is not None:
        source = (
            RETRACTION_SOURCE_CROSSREF_RW
            if retraction.source == "retraction-watch"
            else RETRACTION_SOURCE_CROSSREF_PUBLISHER
        )
        record_external_retraction(
            paper, source=source, retraction_date=retraction.notice_date, now=now
        )
    elif openalex_retracted:
        record_external_retraction(
            paper, source=RETRACTION_SOURCE_OPENALEX, retraction_date=None, now=now
        )


def _integrity(paper: Paper, notices: list[EditorialNotice]) -> dict[str, Any]:
    """Summarise retraction and expression-of-concern status.

    Args:
        paper: The paper (after any retraction was recorded).
        notices: Crossref notices.

    Returns:
        ``{"retracted", "retraction_source", "retraction_date",
        "expression_of_concern", "corrected"}``.
    """
    return {
        "retracted": paper.is_retracted,
        "retraction_source": paper.retraction_source or None,
        "retraction_date": paper.retraction_date.isoformat() if paper.retraction_date else None,
        "expression_of_concern": any(n.is_concern for n in notices),
        "corrected": any(n.is_correction for n in notices),
    }
