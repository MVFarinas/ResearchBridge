"""NCBI E-utilities (PubMed esearch and esummary), JSON responses only.

Politeness: :class:`rbcore.http.PoliteFetcher` spaces requests to
``eutils.ncbi.nlm.nih.gov`` at about 3 per second, NCBI's limit without a key.
An optional ``NCBI_API_KEY`` is sent when configured; it never appears in
error messages. No email address or other personal identifier is sent: the
``tool`` parameter names the project only.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from rbcore.http import FetchError, PoliteFetcher

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL = "ResearchBridge-dev"
ESUMMARY_BATCH = 200


class EutilsError(RuntimeError):
    """Raised when E-utilities returns an error or an unexpected document."""


@dataclass(frozen=True, slots=True)
class PubmedSummary:
    """The fields of a PubMed esummary record the benchmark uses.

    Attributes:
        pmid: PubMed ID.
        title: Article title.
        journal: Journal abbreviation (esummary ``source``).
        pubdate: Publication date as given (e.g. "2021 Feb 2").
        pubtypes: PubMed publication types, in the order given.
        pmcid: PMC ID with prefix, if the record links one.
        doi: DOI, if any.
    """

    pmid: str
    title: str
    journal: str
    pubdate: str
    pubtypes: tuple[str, ...]
    pmcid: str | None
    doi: str | None

    @property
    def year(self) -> int | None:
        """The publication year, if the date starts with one."""
        head = self.pubdate[:4]
        return int(head) if head.isdigit() else None


@dataclass(frozen=True, slots=True)
class SearchResult:
    """What one esearch call returned.

    Attributes:
        pmids: PMIDs in the order esearch returned them (its default sort).
        count: Total hits PubMed reports for the query; when it exceeds
            ``len(pmids)`` the PMIDs are only the first page.
    """

    pmids: list[str]
    count: int

    @property
    def truncated(self) -> bool:
        """Whether PubMed has more hits than were returned."""
        return self.count > len(self.pmids)


class EutilsClient:
    """A small esearch/esummary client over a polite fetcher."""

    def __init__(self, fetcher: PoliteFetcher, api_key: str | None = None) -> None:
        """Create the client.

        Args:
            fetcher: The polite fetcher (shared rate limits and cache).
            api_key: Optional ``NCBI_API_KEY``; never logged.
        """
        self._fetcher = fetcher
        self._api_key = api_key

    def esearch(self, term: str, *, retmax: int = 500) -> SearchResult:
        """Search PubMed.

        No ``sort`` is sent, so when a query has more than ``retmax`` hits the
        PMIDs are the first ``retmax`` in E-utilities' default order; the
        result's ``count`` records how many there were in total.

        Args:
            term: A PubMed query.
            retmax: Maximum PMIDs to return.

        Returns:
            The PMIDs in the order PubMed returns them, and the total count.

        Raises:
            EutilsError: On an error response or unexpected JSON.
        """
        data = self._get("esearch.fcgi", {"db": "pubmed", "term": term, "retmax": str(retmax)})
        result = data.get("esearchresult")
        if not isinstance(result, dict) or "idlist" not in result:
            raise EutilsError(f"unexpected esearch response for {term!r}")
        if result.get("errorlist"):
            raise EutilsError(f"esearch reported errors for {term!r}: {result['errorlist']}")
        pmids = [str(pmid) for pmid in result["idlist"]]
        try:
            count = int(result.get("count", len(pmids)))
        except (TypeError, ValueError):
            raise EutilsError(f"esearch returned a non-numeric count for {term!r}") from None
        return SearchResult(pmids, count)

    def esummary(self, pmids: Sequence[str]) -> dict[str, PubmedSummary]:
        """Fetch summaries in batches.

        Args:
            pmids: PubMed IDs.

        Returns:
            PMID -> summary, for every PMID PubMed returned.

        Raises:
            EutilsError: On an error response or unexpected JSON.
        """
        summaries: dict[str, PubmedSummary] = {}
        for start in range(0, len(pmids), ESUMMARY_BATCH):
            batch = list(pmids[start : start + ESUMMARY_BATCH])
            data = self._get("esummary.fcgi", {"db": "pubmed", "id": ",".join(batch)})
            result = data.get("result")
            if not isinstance(result, dict):
                raise EutilsError("unexpected esummary response")
            for pmid in result.get("uids", []):
                summaries[str(pmid)] = parse_summary(result[str(pmid)])
        return summaries

    def _get(self, endpoint: str, params: dict[str, str]) -> dict[str, Any]:
        """Call one endpoint and return its JSON object.

        Args:
            endpoint: e.g. "esearch.fcgi".
            params: Query parameters (retmode, tool and the key are added).

        Returns:
            The decoded JSON object.

        Raises:
            EutilsError: On a fetch failure (key redacted), a body that is not
                JSON, or non-object JSON.
        """
        query = {**params, "retmode": "json", "tool": TOOL}
        if self._api_key:
            query["api_key"] = self._api_key
        url = f"{EUTILS}/{endpoint}?{urlencode(query)}"
        try:
            body = self._fetcher.get(url)
        except FetchError as exc:
            # The fetcher's message contains the URL; never let the key reach a log.
            message = str(exc).replace(self._api_key, "***") if self._api_key else str(exc)
            raise EutilsError(message) from None
        # An error page or truncated body is an E-utilities failure, not a crash.
        try:
            decoded: Any = json.loads(body)
        except ValueError as exc:
            raise EutilsError(f"{endpoint} returned invalid JSON: {exc}") from None
        if not isinstance(decoded, dict):
            raise EutilsError(f"{endpoint} returned non-object JSON")
        return decoded


def parse_summary(record: dict[str, Any]) -> PubmedSummary:
    """Convert one esummary JSON record.

    Args:
        record: The record for one UID.

    Returns:
        The summary.
    """
    ids = {str(item.get("idtype")): str(item.get("value")) for item in record.get("articleids", [])}
    pmcid = ids.get("pmc")
    return PubmedSummary(
        pmid=str(record.get("uid", "")),
        title=str(record.get("title", "")).strip(),
        journal=str(record.get("source", "")),
        pubdate=str(record.get("pubdate", "")),
        pubtypes=tuple(str(t) for t in record.get("pubtype", [])),
        pmcid=pmcid if pmcid and pmcid.startswith("PMC") else None,
        doi=ids.get("doi"),
    )
