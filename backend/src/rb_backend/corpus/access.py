"""The licence-gated read API: what every reader-facing code path must use.

Views, APIs, search indexing and the generation pipelines (Phases 3-5) read
the corpus only through these functions (or the ``displayable()`` /
``rewriteable()`` queryset methods they wrap). Each one applies the gate, so a
paper, figure or paragraph whose licence fails §1.1, is under review or is not
the current version cannot be returned. :mod:`rb_backend.corpus.accesscheck`
fails the test suite if code outside the corpus internals reads gated models
any other way.

Retracted papers stay displayable but are never rewriteable (the retraction
policy in docs/phase-notes/phase-2.md). Every page or API response that shows
a displayable paper must also show :func:`retraction_notice` prominently
whenever it returns one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from rb_backend.corpus.models import Figure, Paper, PaperVersion, Paragraph, Section
from rb_backend.corpus.querysets import (
    FigureQuerySet,
    PaperQuerySet,
    PaperVersionQuerySet,
    ParagraphQuerySet,
    SectionQuerySet,
)


@dataclass(frozen=True, slots=True)
class RetractionNotice:
    """What a reader must be told about a retracted paper.

    Attributes:
        source: Which source reported the retraction, e.g. ``pmc:is_retracted``.
        retraction_date: Date of the retraction notice, if the source gives
            one (PMC does not).
        recorded_at: When ResearchBridge first recorded the retraction.
    """

    source: str
    retraction_date: date | None
    recorded_at: datetime | None


def retraction_notice(paper: Paper) -> RetractionNotice | None:
    """The retraction notice a reader must see alongside a paper, if any.

    Args:
        paper: The paper (normally one from :func:`displayable_papers`).

    Returns:
        The notice when the paper is retracted, else None.
    """
    if not paper.is_retracted:
        return None
    return RetractionNotice(
        source=paper.retraction_source,
        retraction_date=paper.retraction_date,
        recorded_at=paper.retraction_recorded_at,
    )


def displayable_papers() -> PaperQuerySet:
    """Papers whose current version may be displayed.

    Retracted papers are included; show each one's :func:`retraction_notice`.

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
