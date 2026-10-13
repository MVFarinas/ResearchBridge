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
XML) are deleted. Licence records and superseded blocks remain as provenance.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from rb_backend.corpus.models import (
    BlockScope,
    ContentState,
    Figure,
    LicenceRecord,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
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
    _delete_text(version)


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
    _delete_text(version)

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


def _delete_text(version: PaperVersion) -> None:
    """Delete a version's figures, paragraphs and sections.

    Args:
        version: The version.
    """
    Figure.objects.filter(version=version).delete()
    Paragraph.objects.filter(version=version).delete()
    Section.objects.filter(version=version).delete()
