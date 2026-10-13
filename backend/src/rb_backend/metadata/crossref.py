"""A small Crossref client for editorial notices: retractions and expressions of concern.

Researched 2026-10-13 against live records (see docs/phase-notes/phase-4-5.md):

* An **original article's** record lists the notices about it in
  ``updated-by``: one object per notice with the notice's ``DOI``, a
  Crossmark ``type`` (``retraction``, ``partial_retraction``, ``withdrawal``,
  ``removal``, ``expression_of_concern``, ``correction``, ``erratum``, ...),
  a ``label``, a ``source`` (``retraction-watch`` or ``publisher``), the date
  in ``updated`` and, for Retraction Watch entries, a ``record-id``.
* The **notice's** own record carries the mirror field ``update-to``.
  Since 29 January 2025 Crossref includes the Retraction Watch database in
  these fields (https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/).

So one lookup of the paper's DOI is enough. Crossref metadata is open;
Crossref asks (does not require) that Retraction Watch data be cited, and
the reader does so. Abstracts and references are dropped when trimming.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import quote

from rb_backend.metadata.fetch import get_json
from rb_backend.metadata.jsonvalues import as_int, as_list, as_mapping, as_str
from rbcore.http import PoliteFetcher

BASE_URL = "https://api.crossref.org/works/"
SOURCE = "crossref"

# Crossmark update types, grouped by what the reader says about them.
RETRACTION_TYPES = frozenset({"retraction", "partial_retraction", "withdrawal", "removal"})
CONCERN_TYPES = frozenset({"expression_of_concern"})
CORRECTION_TYPES = frozenset({"correction", "corrigendum", "erratum", "addendum", "clarification"})


class CrossrefClient:
    """Fetches Crossref work records through the polite fetcher."""

    def __init__(self, fetcher: PoliteFetcher, *, base_url: str = BASE_URL) -> None:
        """Create the client.

        Args:
            fetcher: The polite fetcher.
            base_url: API endpoint ending in ``/works/`` (overridable for tests).
        """
        self._fetcher = fetcher
        self._base_url = base_url

    def url(self, doi: str) -> str:
        """The request URL for one DOI.

        Args:
            doi: A bare DOI.

        Returns:
            The URL (no ``mailto``: no personal identifier is ever sent).
        """
        return self._base_url + quote(doi, safe="/()")

    def work(self, doi: str) -> dict[str, Any] | None:
        """Fetch one work's record, trimmed to its DOI and editorial notices.

        Args:
            doi: A bare DOI.

        Returns:
            The trimmed record, or None if Crossref has no such DOI.

        Raises:
            rb_backend.metadata.errors.UpstreamError: If the request fails.
        """
        data = get_json(self._fetcher, self.url(doi), source=SOURCE)
        if data is None:
            return None
        return trim_work(as_mapping(data).get("message"))


def trim_work(raw: object) -> dict[str, Any]:
    """Keep the DOI and the ``updated-by`` notices of a Crossref work.

    Args:
        raw: The ``message`` object of a ``/works/{doi}`` response.

    Returns:
        ``{"DOI": ..., "updated-by": [...]}``.
    """
    work = as_mapping(raw)
    return {"DOI": work.get("DOI"), "updated-by": as_list(work.get("updated-by"))}


@dataclass(frozen=True, slots=True)
class EditorialNotice:
    """One notice about a paper (retraction, expression of concern, correction, ...).

    Attributes:
        kind: Crossmark update type, e.g. "retraction".
        label: Crossref's label, e.g. "Retraction".
        source: "retraction-watch" or "publisher".
        notice_doi: DOI of the notice itself, if given.
        notice_date: Date of the notice, if given.
        record_id: Retraction Watch record ID, if given.
    """

    kind: str
    label: str
    source: str
    notice_doi: str | None
    notice_date: date | None
    record_id: str | None

    @property
    def is_retraction(self) -> bool:
        """Whether the notice retracts, withdraws or removes the paper."""
        return self.kind in RETRACTION_TYPES

    @property
    def is_concern(self) -> bool:
        """Whether the notice is an expression of concern."""
        return self.kind in CONCERN_TYPES

    @property
    def is_correction(self) -> bool:
        """Whether the notice corrects the paper."""
        return self.kind in CORRECTION_TYPES


def parse_notices(trimmed: object) -> list[EditorialNotice]:
    """Read the notices of a trimmed Crossref work, oldest first.

    Args:
        trimmed: The output of :func:`trim_work`.

    Returns:
        Notices with a type; entries without one are skipped.
    """
    notices: list[EditorialNotice] = []
    for item in as_list(as_mapping(trimmed).get("updated-by")):
        entry = as_mapping(item)
        kind = as_str(entry.get("type"))
        if kind is None:
            continue
        notices.append(
            EditorialNotice(
                kind=kind,
                label=as_str(entry.get("label")) or kind.replace("_", " ").capitalize(),
                source=as_str(entry.get("source")) or "",
                notice_doi=(as_str(entry.get("DOI")) or "").lower() or None,
                notice_date=_date(as_mapping(entry.get("updated")).get("date-parts")),
                record_id=as_str(entry.get("record-id")),
            )
        )
    # Sort by date (undated last), then by type for a stable order.
    return sorted(notices, key=lambda n: (n.notice_date or date.max, n.kind))


def _date(date_parts: object) -> date | None:
    """A date from Crossref ``date-parts`` (``[[year, month, day]]``).

    Args:
        date_parts: The value.

    Returns:
        The date (missing month or day default to 1), or None.
    """
    first = as_list(as_list(date_parts)[0]) if as_list(date_parts) else []
    parts = [as_int(part) for part in first[:3]]
    if not parts or parts[0] is None:
        return None
    year = parts[0]
    month = parts[1] if len(parts) > 1 and parts[1] else 1
    day = parts[2] if len(parts) > 2 and parts[2] else 1
    try:
        return date(year, month, day)
    except ValueError:
        return None
