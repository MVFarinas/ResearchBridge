"""The PMC ID Converter: map a DOI or PMID to its PMC ID (and back).

https://pmc.ncbi.nlm.nih.gov/tools/idconv/ — an NCBI service. Requests send
``tool=researchbridge`` and no e-mail address (the service accepts this with a
warning; no personal identifier is ever sent). The lookup flow uses it to find
the PMC record whose licence the primary source states.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlencode

from rb_backend.metadata.fetch import get_json
from rb_backend.metadata.jsonvalues import as_int, as_list, as_mapping, as_str
from rbcore.http import PoliteFetcher

BASE_URL = "https://pmc.ncbi.nlm.nih.gov/tools/idconv/api/v1/articles/"
SOURCE = "pmc-idconv"
TOOL = "researchbridge"

IdType = Literal["doi", "pmid", "pmcid"]


@dataclass(frozen=True, slots=True)
class IdRecord:
    """The identifiers of one article.

    Attributes:
        doi: Bare, lower-cased DOI, if any.
        pmcid: PMC ID with prefix, if any.
        pmid: PubMed ID, if any.
    """

    doi: str | None
    pmcid: str | None
    pmid: str | None


class IdConverter:
    """Looks identifiers up through the polite fetcher."""

    def __init__(self, fetcher: PoliteFetcher, *, base_url: str = BASE_URL) -> None:
        """Create the client.

        Args:
            fetcher: The polite fetcher.
            base_url: API endpoint (overridable for tests).
        """
        self._fetcher = fetcher
        self._base_url = base_url

    def url(self, value: str, idtype: IdType) -> str:
        """The request URL for one identifier.

        Args:
            value: The identifier.
            idtype: Its type.

        Returns:
            The URL.
        """
        params = {"ids": value, "idtype": idtype, "format": "json", "tool": TOOL}
        return f"{self._base_url}?{urlencode(params)}"

    def lookup(self, value: str, idtype: IdType) -> dict[str, Any] | None:
        """Look one identifier up.

        Args:
            value: The identifier.
            idtype: Its type.

        Returns:
            ``{"doi", "pmcid", "pmid"}`` (values may be None), or None when
            the service does not know the identifier.

        Raises:
            rb_backend.metadata.errors.UpstreamError: If the request fails.
        """
        data = get_json(self._fetcher, self.url(value, idtype), source=SOURCE)
        records = as_list(as_mapping(data).get("records"))
        if not records:
            return None
        record = as_mapping(records[0])
        # A per-record error ("Identifier not found in PMC") means unknown.
        if as_str(record.get("status")) == "error":
            return None
        pmid = as_int(record.get("pmid"))
        return {
            "doi": (as_str(record.get("doi")) or "").lower() or None,
            "pmcid": as_str(record.get("pmcid")),
            "pmid": str(pmid) if pmid is not None else as_str(record.get("pmid")),
        }


def parse_record(trimmed: object) -> IdRecord:
    """Read a cached lookup answer.

    Args:
        trimmed: The output of :meth:`IdConverter.lookup`.

    Returns:
        The identifiers.
    """
    record = as_mapping(trimmed)
    return IdRecord(
        doi=as_str(record.get("doi")),
        pmcid=as_str(record.get("pmcid")),
        pmid=as_str(record.get("pmid")),
    )
