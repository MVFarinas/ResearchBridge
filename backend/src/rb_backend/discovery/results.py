"""JSON shapes of search results, shared by corpus and scholarly (OpenAlex) results."""

from __future__ import annotations

from typing import Any

from rb_backend.corpus.models import PaperVersion
from rb_backend.corpus.search_index import author_names
from rb_backend.discovery.availability import (
    Availability,
    corpus_availability,
    external_availability,
)
from rb_backend.discovery.corpus_search import CorpusHit
from rb_backend.discovery.keys import paper_key
from rb_backend.discovery.links import doi_url, scholar_search_url
from rb_backend.generation_status import rewrite_status
from rb_backend.metadata.openalex import OpenAlexWork

MAX_AUTHORS = 5


def corpus_result(hit: CorpusHit) -> dict[str, Any]:
    """Serialise a corpus hit.

    Args:
        hit: The hit (its document's version and paper are loaded).

    Returns:
        A JSON-ready result with ``origin`` "corpus".
    """
    version = hit.document.version
    return {
        "origin": "corpus",
        **_corpus_fields(version, can_rewrite=hit.can_rewrite),
        "snippet": hit.snippet,
    }


def openalex_result(
    work: OpenAlexWork, match: PaperVersion | None, *, can_rewrite: bool
) -> dict[str, Any]:
    """Serialise an OpenAlex work, tagged against the corpus.

    Args:
        work: The work.
        match: The displayable corpus version of the same paper, if any.
        can_rewrite: Whether that version may be rewritten.

    Returns:
        A JSON-ready result with ``origin`` "openalex".
    """
    # In the corpus: the corpus decides the tag; OpenAlex only found it.
    if match is not None:
        return {
            "origin": "openalex",
            **_corpus_fields(match, can_rewrite=can_rewrite),
            "openalex_id": work.openalex_id,
            "licence_reported_by_openalex": work.licence,
            "cited_by_count": work.cited_by_count,
            "lookup_query": None,
            "snippet": "",
        }

    # Elsewhere: OpenAlex's licence is a hint that routes to lookup, never a decision.
    lookup_query = work.doi or work.pmcid or work.pmid
    availability = external_availability(
        openalex_licence=work.licence, has_lookup_id=lookup_query is not None
    )
    return {
        "origin": "openalex",
        "key": None,
        "title": work.title,
        "authors": list(work.authors[:MAX_AUTHORS]),
        "journal": work.journal,
        "published_date": work.publication_date or (str(work.publication_year or "")),
        "doi": work.doi,
        "pmcid": work.pmcid,
        "pmid": work.pmid,
        "availability": availability,
        "rewrite_status": None,
        "licence": None,
        "is_retracted": work.is_retracted,
        "links": _links(work.title, work.doi),
        "openalex_id": work.openalex_id,
        "licence_reported_by_openalex": work.licence,
        "cited_by_count": work.cited_by_count,
        "lookup_query": lookup_query if availability == Availability.MAY_BE_AVAILABLE else None,
        "snippet": "",
    }


def _corpus_fields(version: PaperVersion, *, can_rewrite: bool) -> dict[str, Any]:
    """The fields every result for a corpus paper carries.

    Args:
        version: The displayable version (its paper loaded).
        can_rewrite: Whether it may be rewritten.

    Returns:
        Key, bibliographic fields, availability, rewrite status, licence and links.
    """
    paper = version.paper
    return {
        "key": paper_key(paper),
        "title": version.title,
        "authors": author_names(version.authors)[:MAX_AUTHORS],
        "journal": version.journal_title,
        "published_date": version.published_date,
        "doi": paper.doi,
        "pmcid": paper.pmcid,
        "pmid": paper.pmid,
        "availability": corpus_availability(can_rewrite=can_rewrite),
        "rewrite_status": rewrite_status(can_rewrite=can_rewrite, is_retracted=paper.is_retracted)[
            "status"
        ],
        "licence": version.licence.label,
        "is_retracted": paper.is_retracted,
        "links": _links(version.title, paper.doi),
    }


def _links(title: str | None, doi: str | None) -> dict[str, str | None]:
    """The outbound links of a result.

    Args:
        title: The title.
        doi: The DOI.

    Returns:
        ``{"doi": ..., "scholar": ...}``.
    """
    return {"doi": doi_url(doi), "scholar": scholar_search_url(title=title, doi=doi)}
