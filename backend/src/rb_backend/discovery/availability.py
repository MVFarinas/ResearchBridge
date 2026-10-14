"""What ResearchBridge can offer for a search result (decisions.md §1.5).

Every result carries exactly one tag:

* ``plain_english_available``: in the corpus and its licence permits a
  plain-English rewrite (``can_rewrite``; never for a retracted paper).
* ``original_annotations_only``: in the corpus, display only (e.g. CC BY-ND).
* ``may_be_available``: not in the corpus, but OpenAlex reports an open
  licence. That is a secondary signal only: the reader is sent to lookup,
  which checks eligibility at the primary source before anything is ingested.
* ``original_elsewhere``: not in the corpus; read it at the publisher.

The tag says what the licence allows, not what has been generated: whether a
rewrite exists yet is reported separately (``rewrite_status``).
"""

from __future__ import annotations

from enum import StrEnum

# OpenAlex licence values that name an open licence (cc-by, cc-by-nc-nd, cc0, ...).
_OPEN_PREFIXES = ("cc-", "cc0")
_OPEN_VALUES = frozenset({"public-domain"})


class Availability(StrEnum):
    """The availability tag of a search result."""

    PLAIN_ENGLISH = "plain_english_available"
    ORIGINAL_ANNOTATIONS = "original_annotations_only"
    MAY_BE_AVAILABLE = "may_be_available"
    ELSEWHERE = "original_elsewhere"


def corpus_availability(*, can_rewrite: bool) -> Availability:
    """The tag of a paper in the corpus.

    Args:
        can_rewrite: Whether its current version may be rewritten (the
            caller reads this through the gated access layer).

    Returns:
        PLAIN_ENGLISH or ORIGINAL_ANNOTATIONS.
    """
    return Availability.PLAIN_ENGLISH if can_rewrite else Availability.ORIGINAL_ANNOTATIONS


def external_availability(*, openalex_licence: str | None, has_lookup_id: bool) -> Availability:
    """The tag of a paper outside the corpus, from OpenAlex's licence field.

    Args:
        openalex_licence: The licence OpenAlex reports, if any.
        has_lookup_id: Whether the work has a DOI, PMC ID or PMID that the
            lookup flow can check at the primary source.

    Returns:
        MAY_BE_AVAILABLE for an open licence with a usable identifier,
        otherwise ELSEWHERE.
    """
    licence = (openalex_licence or "").strip().lower()
    is_open = licence.startswith(_OPEN_PREFIXES) or licence in _OPEN_VALUES
    return Availability.MAY_BE_AVAILABLE if is_open and has_lookup_id else Availability.ELSEWHERE
