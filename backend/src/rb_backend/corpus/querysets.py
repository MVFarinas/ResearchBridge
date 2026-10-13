"""Licence-gated querysets: the single access layer for every read path.

``displayable()`` and ``rewriteable()`` are the only sanctioned ways to read
corpus content for anything a reader (or a generation pipeline) will see. The
conditions are built once here, as ``Q`` objects with a relation prefix, so
papers, versions, sections, paragraphs, figures and annotations all apply
exactly the same rules:

* A **version** is displayable when it is the paper's current version, its
  gate status is approved and its effective ``can_display`` is true. Only the
  current version is ever served (the PMC terms ask redistributors to keep
  data current). It is rewriteable when it is also ``can_rewrite`` and the
  paper is not retracted (decisions.md §1.1; retraction handling in
  docs/phase-notes/phase-2.md).
* A **part** (paragraph or figure/table) is displayable when its own gate
  decision allows display *and* its version is displayable, and rewriteable
  when both its own decision and its version's allow rewriting. A part can
  therefore never be more open than its paper.

The stored permissions are themselves guarded by database check constraints
(:func:`rb_backend.corpus.models.gated.gate_constraints`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from django.db import models
from django.db.models import Q

from rb_backend.corpus.models.gated import GateStatus

if TYPE_CHECKING:
    # Used in the quoted QuerySet type arguments below.
    from rb_backend.corpus.models.papers import (  # noqa: F401
        Figure,
        Paper,
        PaperVersion,
        Paragraph,
        Section,
    )


def own_displayable_q(prefix: str = "") -> Q:
    """Conditions on a gated row's own decision for display.

    Args:
        prefix: Relation path to the gated row, e.g. ``"paragraph__"``.

    Returns:
        A ``Q``: approved and ``can_display``.
    """
    return Q(**{f"{prefix}gate_status": GateStatus.APPROVED, f"{prefix}can_display": True})


def own_rewriteable_q(prefix: str = "") -> Q:
    """Conditions on a gated row's own decision for rewriting.

    Args:
        prefix: Relation path to the gated row.

    Returns:
        A ``Q``: displayable by its own decision and ``can_rewrite``.
    """
    return own_displayable_q(prefix) & Q(**{f"{prefix}can_rewrite": True})


def version_displayable_q(prefix: str = "") -> Q:
    """Conditions for a paper version to be displayable.

    Args:
        prefix: Relation path to the version, e.g. ``"version__"``.

    Returns:
        A ``Q``: current, approved and ``can_display``.
    """
    return Q(**{f"{prefix}is_current": True}) & own_displayable_q(prefix)


def version_rewriteable_q(prefix: str = "") -> Q:
    """Conditions for a paper version to be rewriteable.

    Args:
        prefix: Relation path to the version.

    Returns:
        A ``Q``: displayable, ``can_rewrite`` and the paper is not retracted.
    """
    return (
        version_displayable_q(prefix)
        & Q(**{f"{prefix}can_rewrite": True})
        & Q(**{f"{prefix}paper__is_retracted": False})
    )


def part_displayable_q(prefix: str = "") -> Q:
    """Conditions for a paragraph or figure to be displayable.

    Args:
        prefix: Relation path to the part, e.g. ``"paragraph__"``.

    Returns:
        A ``Q``: the part's own decision allows display and its version is
        displayable.
    """
    return own_displayable_q(prefix) & version_displayable_q(f"{prefix}version__")


def part_rewriteable_q(prefix: str = "") -> Q:
    """Conditions for a paragraph or figure to be rewriteable.

    Args:
        prefix: Relation path to the part.

    Returns:
        A ``Q``: the part's own decision and its version both allow rewriting.
    """
    return own_rewriteable_q(prefix) & version_rewriteable_q(f"{prefix}version__")


class PaperQuerySet(models.QuerySet["Paper"]):
    """Querysets of papers with the licence-gated read methods."""

    def displayable(self) -> Self:
        """Papers whose current version may be displayed.

        Returns:
            The filtered queryset. At most one current version exists per
            paper (a unique constraint), so the join never duplicates rows.
        """
        return self.filter(version_displayable_q("versions__"))

    def rewriteable(self) -> Self:
        """Papers whose current version may be rewritten (and not retracted).

        Returns:
            The filtered queryset.
        """
        return self.filter(version_rewriteable_q("versions__"))


class PaperVersionQuerySet(models.QuerySet["PaperVersion"]):
    """Querysets of paper versions with the licence-gated read methods."""

    def displayable(self) -> Self:
        """Current, approved versions that may be displayed.

        Returns:
            The filtered queryset.
        """
        return self.filter(version_displayable_q())

    def rewriteable(self) -> Self:
        """Displayable versions that may also be rewritten.

        Returns:
            The filtered queryset.
        """
        return self.filter(version_rewriteable_q())


class SectionQuerySet(models.QuerySet["Section"]):
    """Querysets of sections; a section title follows its version's gate."""

    def displayable(self) -> Self:
        """Sections of displayable versions.

        Returns:
            The filtered queryset.
        """
        return self.filter(version_displayable_q("version__"))

    def rewriteable(self) -> Self:
        """Sections of rewriteable versions.

        Returns:
            The filtered queryset.
        """
        return self.filter(version_rewriteable_q("version__"))


class ParagraphQuerySet(models.QuerySet["Paragraph"]):
    """Querysets of paragraphs with the licence-gated read methods."""

    def displayable(self) -> Self:
        """Paragraphs that may be displayed (own decision and version).

        Returns:
            The filtered queryset.
        """
        return self.filter(part_displayable_q())

    def rewriteable(self) -> Self:
        """Paragraphs that may be rewritten (own decision and version).

        Returns:
            The filtered queryset.
        """
        return self.filter(part_rewriteable_q())


class FigureQuerySet(models.QuerySet["Figure"]):
    """Querysets of figures and tables with the licence-gated read methods."""

    def displayable(self) -> Self:
        """Figures and tables that may be displayed (own decision and version).

        Returns:
            The filtered queryset.
        """
        return self.filter(part_displayable_q())

    def rewriteable(self) -> Self:
        """Figures and tables whose captions may be rewritten.

        Returns:
            The filtered queryset.
        """
        return self.filter(part_rewriteable_q())
