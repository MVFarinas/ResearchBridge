"""The search service behind entry point 1 (decisions.md §1.5).

One search returns two lists:

* **corpus**: papers ResearchBridge can show, from Postgres full-text search;
* **openalex**: the wider scholarly record from OpenAlex, each work tagged
  against the corpus (a work already in the corpus takes the corpus tag).

OpenAlex is optional. Without ``OPENALEX_API_KEY`` it allows a small daily
budget; when it refuses or fails, the response carries the corpus results and
a notice instead. OpenAlex answers are cached and carry an "as of" date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import Q

from rb_backend.corpus import access
from rb_backend.corpus.models import PaperVersion
from rb_backend.discovery.corpus_search import (
    AvailabilityFilter,
    CorpusSearch,
    SortOrder,
    search_corpus,
)
from rb_backend.discovery.results import corpus_result, openalex_result
from rb_backend.metadata.errors import UpstreamError, UpstreamRefusedError
from rb_backend.metadata.openalex import OpenAlexWork, SearchRequest, WorkType, parse_work
from rb_backend.metadata.services import MetadataClients, openalex_search

PER_PAGE = 10

NOTICE_REFUSED = (
    "The wider scholarly search (OpenAlex) is not available right now: it declined the "
    "request, usually because its free daily allowance is used up. Showing papers from "
    "ResearchBridge only."
)
NOTICE_UNAVAILABLE = (
    "The wider scholarly search (OpenAlex) could not be reached. Showing papers from "
    "ResearchBridge only."
)


@dataclass(frozen=True, slots=True)
class SearchParams:
    """A reader's search.

    Attributes:
        query: Keywords.
        year_from: Earliest year, if any.
        year_to: Latest year, if any.
        availability: Restrict corpus results to one tag, if any.
        work_types: Restrict OpenAlex results to these types (empty: any).
        sort: Relevance, newest or oldest.
        page: 1-based page (applies to both lists).
        include_openalex: Whether to query OpenAlex at all.
    """

    query: str
    year_from: int | None = None
    year_to: int | None = None
    availability: AvailabilityFilter | None = None
    work_types: tuple[WorkType, ...] = ()
    sort: SortOrder = "relevance"
    page: int = 1
    include_openalex: bool = True


def run_search(
    params: SearchParams, clients: MetadataClients, *, now: datetime | None = None
) -> dict[str, Any]:
    """Search the corpus and, when possible, OpenAlex.

    Args:
        params: The search.
        clients: Metadata clients.
        now: Current time.

    Returns:
        ``{"query", "page", "corpus": {...}, "openalex": {...}}``.
    """
    corpus_page = search_corpus(
        CorpusSearch(
            query=params.query,
            year_from=params.year_from,
            year_to=params.year_to,
            availability=params.availability,
            sort=params.sort,
            page=params.page,
            per_page=PER_PAGE,
        )
    )
    return {
        "query": params.query,
        "page": params.page,
        "per_page": PER_PAGE,
        "corpus": {
            "total": corpus_page.total,
            "results": [corpus_result(hit) for hit in corpus_page.hits],
        },
        "openalex": _openalex_section(params, clients, now=now),
    }


def _openalex_section(
    params: SearchParams, clients: MetadataClients, *, now: datetime | None
) -> dict[str, Any]:
    """Search OpenAlex and tag its results, degrading to a notice on failure.

    Args:
        params: The search.
        clients: Metadata clients.
        now: Current time.

    Returns:
        ``{"status", "notice", "as_of", "stale", "total", "results",
        "has_key"}``; status is ok, skipped, refused or unavailable.
    """
    base: dict[str, Any] = {
        "notice": "",
        "as_of": None,
        "stale": False,
        "total": 0,
        "results": [],
        "has_key": clients.openalex.has_key,
    }
    if not params.include_openalex:
        return {**base, "status": "skipped"}

    request = SearchRequest(
        query=params.query,
        year_from=params.year_from,
        year_to=params.year_to,
        work_types=params.work_types,
        sort=params.sort,
        page=params.page,
        per_page=PER_PAGE,
    )
    # A refusal (no key, budget spent) and an outage get different notices.
    try:
        answer = openalex_search(clients, request, now=now)
    except UpstreamRefusedError:
        return {**base, "status": "refused", "notice": NOTICE_REFUSED}
    except UpstreamError:
        return {**base, "status": "unavailable", "notice": NOTICE_UNAVAILABLE}

    payload = answer.payload if isinstance(answer.payload, dict) else {}
    works = [parse_work(item) for item in payload.get("results", [])]
    return {
        **base,
        "status": "ok",
        "notice": "Showing results saved earlier; a refresh failed." if answer.stale else "",
        "as_of": answer.as_of.isoformat(),
        "stale": answer.stale,
        "total": payload.get("count", 0),
        "results": _tag(works),
    }


def _tag(works: list[OpenAlexWork]) -> list[dict[str, Any]]:
    """Serialise OpenAlex works, matching each against the corpus.

    Args:
        works: Works in OpenAlex's order.

    Returns:
        Results; a work held in the corpus carries the corpus tag and key.
    """
    # One gated query finds every corpus paper on the page, by any identifier.
    dois = {w.doi for w in works if w.doi}
    pmcids = {w.pmcid for w in works if w.pmcid}
    pmids = {w.pmid for w in works if w.pmid}
    versions = list(
        access.displayable_versions()
        .filter(Q(paper__doi__in=dois) | Q(paper__pmcid__in=pmcids) | Q(paper__pmid__in=pmids))
        .select_related("paper")
    )
    rewriteable = set(
        access.rewriteable_versions()
        .filter(pk__in=[v.pk for v in versions])
        .values_list("pk", flat=True)
    )
    return [
        openalex_result(work, match, can_rewrite=match is not None and match.pk in rewriteable)
        for work in works
        for match in [_match(work, versions)]
    ]


def _match(work: OpenAlexWork, versions: list[PaperVersion]) -> PaperVersion | None:
    """The corpus version of the same paper as an OpenAlex work.

    Args:
        work: The work.
        versions: Displayable versions found for the page.

    Returns:
        The match (by DOI, then PMC ID, then PMID), or None.
    """
    for version in versions:
        paper = version.paper
        if (
            (work.doi and paper.doi == work.doi)
            or (work.pmcid and paper.pmcid == work.pmcid)
            or (work.pmid and paper.pmid == work.pmid)
        ):
            return version
    return None
