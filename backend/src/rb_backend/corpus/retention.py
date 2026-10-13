"""Remove stored full text that the licence gate no longer allows us to hold.

decisions.md §1.1 says content that is not openly licensed is never ingested.
Two situations remove text that was stored earlier:

* :func:`purge_content`: the source's own licence code refuses the version
  (e.g. PMC ``TDM``). The XML is no longer evidence for anything, so every
  JATS permissions block is superseded too.
* :func:`remove_rejected_text`: the gate rejected the version on the
  evidence it holds (an all-rights-reserved JATS licence, or a reviewer's
  rejection). The article-level and unattached permissions blocks are that
  evidence, so they stay active and a later re-evaluation reaches the same
  decision; only the text and the part-level blocks go.

In both cases sections, paragraphs and figures (with their original JATS
XML) are deleted. Licence records and superseded blocks remain as provenance,
and so do licence reviews: :func:`delete_parts` supersedes the open reviews of
the parts it deletes, and resolved ones lose only their link to the part row
(they keep its stable ID), so a reviewer's decision is never deleted.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from django.db.models import Q, QuerySet

from rb_backend.corpus.models import (
    BlockScope,
    ContentState,
    Figure,
    LicenceRecord,
    LicenceReview,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
    ReviewStatus,
    Section,
)

# Block scopes that belong to a part (figure, table or paragraph) of the text.
PART_SCOPES: tuple[str, ...] = (BlockScope.FIGURE.value, BlockScope.PARAGRAPH.value)


def purge_content(version: PaperVersion, *, superseded_at: datetime) -> None:
    """Remove a version's stored full text and supersede all its JATS blocks.

    Used when the source's licence code alone refuses the version, so the
    XML will not be fetched again while that code stands.

    Args:
        version: The version.
        superseded_at: Time to record on the superseded blocks.
    """
    supersede_blocks(version, superseded_at)
    _delete_text(version, superseded_at)


def remove_rejected_text(version: PaperVersion, *, superseded_at: datetime) -> bool:
    """Remove the text of a version the gate has rejected, keeping its evidence.

    A version whose text was parsed moves to :attr:`ContentState.REMOVED`, so
    ingestion does not fetch the same XML again while the gate still rejects
    it. Any other content state (for example a failed parse, which is itself
    review evidence) is left as it is.

    Args:
        version: The version (its content state is saved if it changes).
        superseded_at: Time to record on the superseded part-level blocks.

    Returns:
        True if anything was removed or the content state changed.
    """
    # Nothing stored and nothing to record: keep the call cheap and idempotent.
    has_text = (
        Section.objects.filter(version=version).exists()
        or Figure.objects.filter(version=version).exists()
    )
    if not has_text and version.content_state != ContentState.PARSED:
        return False

    # Part-level blocks describe parts that are about to be deleted.
    supersede_blocks(version, superseded_at, scopes=PART_SCOPES)
    _delete_text(version, superseded_at)

    # Remember that the text was removed on purpose, not never fetched.
    if version.content_state == ContentState.PARSED:
        version.content_state = ContentState.REMOVED
        version.content_error = ""
        version.save(update_fields=["content_state", "content_error", "updated_at"])
    return True


def supersede_blocks(
    version: PaperVersion, when: datetime, *, scopes: Collection[str] | None = None
) -> None:
    """Mark a version's active JATS blocks (and their licence records) superseded.

    Args:
        version: The version.
        when: The supersession time.
        scopes: Only blocks with these scopes; None for every block.
    """
    blocks = PermissionsBlockRecord.objects.active().filter(version=version)
    records = LicenceRecord.objects.active().filter(version=version, block__isnull=False)
    if scopes is not None:
        blocks = blocks.filter(scope__in=list(scopes))
        records = records.filter(block__scope__in=list(scopes))
    records.update(superseded_at=when)
    blocks.update(superseded_at=when)


def delete_parts(
    *,
    figures: QuerySet[Figure] | None = None,
    paragraphs: QuerySet[Paragraph] | None = None,
    when: datetime,
) -> None:
    """Delete figures and paragraphs without losing their licence reviews.

    Every deletion of a part goes through here. An open review of a deleted
    part can no longer be answered, so it is superseded; a resolved review is
    the audit trail of a human decision, so the database only clears its link
    to the part row (``on_delete=SET_NULL``) and it keeps the part's stable ID.

    Args:
        figures: Figures and tables to delete, or None.
        paragraphs: Paragraphs to delete, or None.
        when: Time to record on the superseded reviews.
    """
    # Retire the questions about these parts before the rows go.
    open_reviews = Q()
    if figures is not None:
        open_reviews |= Q(figure__in=figures.values("pk"))
    if paragraphs is not None:
        open_reviews |= Q(paragraph__in=paragraphs.values("pk"))
    if open_reviews:
        LicenceReview.objects.filter(open_reviews, status=ReviewStatus.OPEN).update(
            status=ReviewStatus.SUPERSEDED, updated_at=when
        )

    # Then delete the parts; resolved reviews are detached, not deleted.
    if figures is not None:
        figures.delete()
    if paragraphs is not None:
        paragraphs.delete()


def _delete_text(version: PaperVersion, when: datetime) -> None:
    """Delete a version's figures, paragraphs and sections.

    Args:
        version: The version.
        when: Time to record on the reviews this supersedes.
    """
    delete_parts(
        figures=Figure.objects.filter(version=version),
        paragraphs=Paragraph.objects.filter(version=version),
        when=when,
    )
    Section.objects.filter(version=version).delete()
