"""Full-text search over the licence-gated corpus (PostgreSQL ``tsvector``).

Queries use ``websearch_to_tsquery`` (quoted phrases, ``or``, ``-exclude``),
rank with ``ts_rank`` over the weighted document (title > abstract > authors
and journal), and read documents only through
``rb_backend.corpus.access.displayable_search_documents``, so a paper that
fails the gate is never found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.db.models import F
from django.db.models.expressions import OrderBy

from rb_backend.corpus import access
from rb_backend.corpus.models import SEARCH_CONFIG, SearchDocument

AvailabilityFilter = Literal["plain_english_available", "original_annotations_only"]
SortOrder = Literal["relevance", "newest", "oldest"]

# Private-use characters mark the matched words in snippets; the web app turns
# them into <mark> elements, so no HTML ever travels in the API.
HIGHLIGHT_START = ""
HIGHLIGHT_STOP = ""


@dataclass(frozen=True, slots=True)
class CorpusSearch:
    """One corpus search.

    Attributes:
        query: Keywords (web-search syntax).
        year_from: Earliest publication year, if any.
        year_to: Latest publication year, if any.
        availability: Restrict to one availability tag, if any.
        sort: Relevance, newest first or oldest first.
        page: 1-based page.
        per_page: Results per page.
    """

    query: str
    year_from: int | None = None
    year_to: int | None = None
    availability: AvailabilityFilter | None = None
    sort: SortOrder = "relevance"
    page: int = 1
    per_page: int = 10


@dataclass(frozen=True, slots=True)
class CorpusHit:
    """One matching document, with whether its paper may be rewritten.

    Attributes:
        document: The search document (its version and paper are loaded).
        snippet: Matching abstract text with highlight markers ("" if none).
        can_rewrite: Whether the paper may be rewritten.
    """

    document: SearchDocument
    snippet: str
    can_rewrite: bool


@dataclass(frozen=True, slots=True)
class CorpusPage:
    """One page of corpus results.

    Attributes:
        total: Matching documents in all.
        hits: This page's hits.
    """

    total: int
    hits: list[CorpusHit]


def search_corpus(search: CorpusSearch) -> CorpusPage:
    """Run a corpus search.

    Args:
        search: The search.

    Returns:
        The page of results.
    """
    query = SearchQuery(search.query, search_type="websearch", config=SEARCH_CONFIG)
    rewriteable = access.displayable_search_documents().filter(
        pk__in=SearchDocument.objects.rewriteable().values("pk")
    )

    # Matching, gated documents, filtered by year and availability.
    documents = access.displayable_search_documents().filter(document=query)
    if search.year_from is not None:
        documents = documents.filter(published_year__gte=search.year_from)
    if search.year_to is not None:
        documents = documents.filter(published_year__lte=search.year_to)
    if search.availability == "plain_english_available":
        documents = documents.filter(pk__in=rewriteable.values("pk"))
    elif search.availability == "original_annotations_only":
        documents = documents.exclude(pk__in=rewriteable.values("pk"))

    # Rank, order and page.
    ranked = documents.annotate(rank=SearchRank(F("document"), query)).order_by(
        *_ordering(search.sort)
    )
    total = ranked.count()
    start = (search.page - 1) * search.per_page
    page = list(
        ranked.select_related("version", "version__paper").annotate(
            snippet=SearchHeadline(
                "abstract",
                query,
                config=SEARCH_CONFIG,
                start_sel=HIGHLIGHT_START,
                stop_sel=HIGHLIGHT_STOP,
                max_words=40,
                min_words=15,
                max_fragments=2,
                fragment_delimiter=" … ",
            )
        )[start : start + search.per_page]
    )

    # Which of this page's papers may be rewritten (one query for the page).
    rewrite_ids = set(
        rewriteable.filter(pk__in=[doc.pk for doc in page]).values_list("pk", flat=True)
    )
    hits = [CorpusHit(doc, _snippet(doc), doc.pk in rewrite_ids) for doc in page]
    return CorpusPage(total=total, hits=hits)


def _snippet(document: SearchDocument) -> str:
    """The highlighted abstract snippet annotated on a document.

    Args:
        document: A document from :func:`search_corpus`'s annotated query.

    Returns:
        The snippet, or "" when the document has no abstract.
    """
    snippet = getattr(document, "snippet", "")
    return snippet if document.abstract and isinstance(snippet, str) else ""


def _ordering(sort: SortOrder) -> list[OrderBy | str]:
    """The ``order_by`` terms for a sort order.

    Args:
        sort: Relevance, newest or oldest.

    Returns:
        Ordering expressions; ties are broken so pages are stable. Dates are
        ISO strings, so they sort correctly as text ("" sorts last when
        newest first).
    """
    if sort == "newest":
        return [F("published_date").desc(), "title", "pk"]
    if sort == "oldest":
        return [F("published_year").asc(nulls_last=True), "published_date", "title", "pk"]
    return [F("rank").desc(), F("published_date").desc(), "pk"]
