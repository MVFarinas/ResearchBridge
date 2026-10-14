"""The full-text search document kept for each paper version (decisions.md §1.6).

One :class:`SearchDocument` per version holds a weighted PostgreSQL
``tsvector`` built from the title (weight A), the abstract (B) and the
authors and journal (C), with a GIN index. It is rebuilt whenever the gate
runs (:func:`rb_backend.corpus.search_index.refresh_search_document`), so it
follows ingestion, re-checks and review resolutions.

The document holds text derived from the paper, so it is a gated model like
the content it indexes: reader-facing code reads it only through
``SearchDocument.objects.displayable()``, which applies the version's licence
gate at query time. A stale row for a version that later stops being
displayable can therefore never surface in results.
"""

from __future__ import annotations

from typing import Self

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from rb_backend.corpus.models.papers import PaperVersion
from rb_backend.corpus.querysets import version_displayable_q, version_rewriteable_q

# The text search configuration used to build and to query documents.
SEARCH_CONFIG = "english"


class SearchDocumentQuerySet(models.QuerySet["SearchDocument"]):
    """Querysets of search documents with the licence-gated read methods."""

    def displayable(self) -> Self:
        """Documents of versions that may be displayed.

        Returns:
            The filtered queryset.
        """
        return self.filter(version_displayable_q("version__"))

    def rewriteable(self) -> Self:
        """Documents of versions that may be rewritten.

        Returns:
            The filtered queryset.
        """
        return self.filter(version_rewriteable_q("version__"))


class SearchDocument(models.Model):
    """The searchable text of one paper version.

    Attributes:
        version: The paper version indexed.
        title: The title as indexed.
        abstract: The abstract paragraphs, joined, as indexed.
        authors: Author names, joined.
        journal: Journal title.
        published_date: ISO 8601 date at the precision available.
        published_year: The year, for filtering; None if unknown.
        document: The weighted ``tsvector``.
        updated_at: When the document was last rebuilt.
    """

    version = models.OneToOneField(
        PaperVersion, on_delete=models.CASCADE, related_name="search_document"
    )
    title = models.TextField(blank=True)
    abstract = models.TextField(blank=True)
    authors = models.TextField(blank=True)
    journal = models.TextField(blank=True)
    published_date = models.CharField(max_length=10, blank=True)
    published_year = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    document = SearchVectorField(null=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SearchDocumentQuerySet.as_manager()

    class Meta:
        """A GIN index makes ``document @@ query`` fast."""

        indexes = [GinIndex(fields=["document"], name="searchdocument_document_gin")]

    def __str__(self) -> str:
        """Return the indexed version's ID."""
        return f"search document for version {self.version_id}"
