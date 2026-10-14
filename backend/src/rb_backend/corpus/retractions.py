"""Record retractions reported by sources other than PMC (Crossref, OpenAlex).

PMC's ``is_retracted`` flag is recorded at ingestion
(:mod:`rb_backend.ingestion.pipeline`). The credibility lookups of Phase 5
also see Crossref ``updated-by`` retraction notices (which carry Retraction
Watch data) and OpenAlex ``is_retracted`` (itself drawn from Retraction
Watch). When either reports a retraction the paper is marked retracted here,
which makes it non-rewriteable through the gated querysets.

A retraction recorded from these sources is never cleared automatically: a
reinstatement is rare and needs a human, and failing towards "retracted"
only withholds a rewrite, never the original or the notice.
"""

from __future__ import annotations

from datetime import date, datetime

from rb_backend.corpus.models import Paper

# Sources a retraction may be recorded from, as stored in Paper.retraction_source.
RETRACTION_SOURCE_CROSSREF_RW = "crossref:retraction-watch"
RETRACTION_SOURCE_CROSSREF_PUBLISHER = "crossref:publisher"
RETRACTION_SOURCE_OPENALEX = "openalex:is_retracted"


def record_external_retraction(
    paper: Paper, *, source: str, retraction_date: date | None, now: datetime
) -> bool:
    """Mark a paper retracted on the word of an external source.

    Args:
        paper: The paper.
        source: One of the ``RETRACTION_SOURCE_*`` values.
        retraction_date: The notice's date, when the source gives one.
        now: Current time (recorded as when ResearchBridge learnt of it).

    Returns:
        True if the paper was changed; False if it was already marked
        retracted (the first source to report it is kept, but a missing
        date is filled in).
    """
    # Already retracted: keep the first source, only fill a missing date.
    if paper.is_retracted:
        if paper.retraction_date is None and retraction_date is not None:
            paper.retraction_date = retraction_date
            paper.save(update_fields=["retraction_date", "updated_at"])
            return True
        return False

    paper.is_retracted = True
    paper.retraction_source = source
    paper.retraction_date = retraction_date
    paper.retraction_recorded_at = now
    paper.save(
        update_fields=[
            "is_retracted",
            "retraction_source",
            "retraction_date",
            "retraction_recorded_at",
            "updated_at",
        ]
    )
    return True
