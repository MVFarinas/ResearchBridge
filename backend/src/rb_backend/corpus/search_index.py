"""Build and refresh the full-text search document of a paper version.

The gate calls :func:`refresh_search_document` at the end of every
evaluation, inside the same transaction, so the index follows every change
to a version's text or licence. Whether a document may be *returned* is not
decided here: queries go through ``SearchDocument.objects.displayable()``.
A version with no stored text (rejected, removed or not yet fetched) keeps a
title-only document, which the gated query never returns while the version
is not displayable.

``manage.py rebuild_search_index`` rebuilds every document (for versions
ingested before the index existed).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from django.contrib.postgres.search import SearchVector
from django.db.models import Value
from django.db.models.expressions import CombinedExpression

from rb_backend.corpus.models import SEARCH_CONFIG, PaperVersion, Paragraph, SearchDocument
from rb_backend.corpus.querysets import own_displayable_q

# rbcore gives abstract sections IDs starting "abs" (abs1, abs2, ...); nested
# sections of a structured abstract keep that prefix.
_ABSTRACT_SECTION = re.compile(r"^abs\d+")
_YEAR = re.compile(r"^(\d{4})")


def refresh_search_document(version: PaperVersion) -> SearchDocument:
    """Create or rebuild the search document of one version.

    Args:
        version: The version (its stored metadata and paragraphs are read).

    Returns:
        The saved document.
    """
    # Gather the text from the stored rows (internal read: this module is
    # part of the trusted corpus internals and the result is gated at query time).
    abstract = " ".join(_abstract_paragraphs(version))
    authors = " ".join(author_names(version.authors))
    year = published_year(version.published_date)

    document, _ = SearchDocument.objects.update_or_create(
        version=version,
        defaults={
            "title": version.title,
            "abstract": abstract,
            "authors": authors,
            "journal": version.journal_title,
            "published_date": version.published_date,
            "published_year": year,
        },
    )
    # Weighted vector computed by Postgres from the stored columns.
    SearchDocument.objects.filter(pk=document.pk).update(document=_weighted_vector())
    return document


def rebuild_all(versions: Iterable[PaperVersion]) -> int:
    """Rebuild the documents of many versions.

    Args:
        versions: The versions.

    Returns:
        How many documents were rebuilt.
    """
    count = 0
    for version in versions:
        refresh_search_document(version)
        count += 1
    return count


def _weighted_vector() -> CombinedExpression:
    """The weighted ``tsvector`` expression over a document's own columns.

    Returns:
        Title (A) + abstract (B) + authors and journal (C).
    """
    return (
        SearchVector("title", weight="A", config=Value(SEARCH_CONFIG))
        + SearchVector("abstract", weight="B", config=Value(SEARCH_CONFIG))
        + SearchVector("authors", "journal", weight="C", config=Value(SEARCH_CONFIG))
    )


def _abstract_paragraphs(version: PaperVersion) -> list[str]:
    """The text of a version's abstract paragraphs, in document order.

    Args:
        version: The version.

    Returns:
        Texts of the abstract paragraphs that may be displayed on their own terms.
    """
    # Only paragraphs whose own decision allows display are indexed, so the
    # snippets search shows never include a paragraph licensed more narrowly
    # than its paper; the version itself is gated when the index is queried.
    rows = (
        Paragraph.objects.filter(own_displayable_q(), version=version)
        .order_by("position")
        .values_list("section__stable_id", "text")
    )
    return [text for section_id, text in rows if _ABSTRACT_SECTION.match(section_id)]


def author_names(authors: object) -> list[str]:
    """Display names from the stored author list.

    Args:
        authors: The ``PaperVersion.authors`` JSON (a list of objects with a
            ``name`` or ``collab``); anything else yields nothing.

    Returns:
        Names in order, skipping entries without one.
    """
    if not isinstance(authors, list):
        return []
    names: list[str] = []
    for author in authors:
        if isinstance(author, Mapping):
            name = _first_text(author, ("name", "collab"))
            if name:
                names.append(name)
    return names


def _first_text(mapping: Mapping[str, Any], keys: tuple[str, ...]) -> str:
    """The first non-empty string value among ``keys``.

    Args:
        mapping: A JSON object.
        keys: Keys to try in order.

    Returns:
        The stripped value, or "".
    """
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def published_year(published_date: str) -> int | None:
    """The year of an ISO 8601 date of any precision.

    Args:
        published_date: ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD`` (or "").

    Returns:
        The year, or None.
    """
    match = _YEAR.match(published_date or "")
    return int(match.group(1)) if match else None
