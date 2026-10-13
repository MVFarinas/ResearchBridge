"""The licence-gated read API: what every reader-facing code path must use.

Views, APIs, search indexing and the generation pipelines (Phases 3-5) read
the corpus only through these functions (or the ``displayable()`` /
``rewriteable()`` queryset methods they wrap). Each one applies the gate, so a
paper, figure or paragraph whose licence fails §1.1, is under review or is not
the current version cannot be returned. :mod:`rb_backend.corpus.accesscheck`
fails the test suite if code outside the corpus internals reads gated models
any other way.
"""

from __future__ import annotations

from rb_backend.corpus.models import Figure, Paper, PaperVersion, Paragraph, Section
from rb_backend.corpus.querysets import (
    FigureQuerySet,
    PaperQuerySet,
    PaperVersionQuerySet,
    ParagraphQuerySet,
    SectionQuerySet,
)


def displayable_papers() -> PaperQuerySet:
    """Papers whose current version may be displayed.

    Returns:
        A queryset of papers.
    """
    return Paper.objects.displayable()


def rewriteable_papers() -> PaperQuerySet:
    """Papers whose current version may be rewritten (and are not retracted).

    Returns:
        A queryset of papers.
    """
    return Paper.objects.rewriteable()


def displayable_version(paper: Paper) -> PaperVersion | None:
    """The version of a paper to display, if it may be displayed.

    Args:
        paper: The paper.

    Returns:
        Its current version when that passes the gate, else None.
    """
    return PaperVersion.objects.displayable().filter(paper=paper).first()


def displayable_versions() -> PaperVersionQuerySet:
    """Every displayable (current, approved) version.

    Returns:
        A queryset of versions.
    """
    return PaperVersion.objects.displayable()


def rewriteable_versions() -> PaperVersionQuerySet:
    """Every version that may be rewritten.

    Returns:
        A queryset of versions.
    """
    return PaperVersion.objects.rewriteable()


def displayable_sections(version: PaperVersion) -> SectionQuerySet:
    """Sections (titles and structure) of a version, if it may be displayed.

    Args:
        version: The version.

    Returns:
        Its sections in document order; empty unless it is displayable.
    """
    return Section.objects.displayable().filter(version=version).order_by("position")


def displayable_paragraphs(version: PaperVersion) -> ParagraphQuerySet:
    """Paragraphs of a version that may be displayed.

    Args:
        version: The version.

    Returns:
        Displayable paragraphs in document order (paragraphs with their own
        restrictive licence are left out).
    """
    return Paragraph.objects.displayable().filter(version=version).order_by("position")


def rewriteable_paragraphs(version: PaperVersion) -> ParagraphQuerySet:
    """Paragraphs of a version that may be rewritten.

    Args:
        version: The version.

    Returns:
        Rewriteable paragraphs in document order.
    """
    return Paragraph.objects.rewriteable().filter(version=version).order_by("position")


def displayable_figures(version: PaperVersion) -> FigureQuerySet:
    """Figures and tables of a version that may be displayed.

    Args:
        version: The version.

    Returns:
        Displayable figures and tables in document order (figure-level
        licence overrides applied).
    """
    return Figure.objects.displayable().filter(version=version).order_by("position")
