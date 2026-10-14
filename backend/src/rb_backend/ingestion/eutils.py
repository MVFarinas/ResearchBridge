"""Discover PMC articles with NCBI E-utilities ESearch (the README's "ESearch-S3 pipeline").

The PMC Cloud Service README recommends ESearch to turn a query into PMC IDs,
then the bucket for the files. Requests go through
:class:`rbcore.http.PoliteFetcher`, which limits ``eutils.ncbi.nlm.nih.gov``
to about 3 requests per second (NCBI's limit without a key). An
``NCBI_API_KEY``, when set in the environment, is sent as ``api_key``; it is
never logged, and it is redacted from the errors :func:`search_pmc` raises
(the fetcher's messages embed the full request URL). The ``tool`` parameter
names the project; no e-mail address or other personal identifier is ever sent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlencode

from rbcore.http import FetchError, PoliteFetcher

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
TOOL_NAME = "researchbridge"
# Replaces an API key in error messages.
REDACTED = "[redacted]"
# ESearch returns at most 10,000 IDs per request.
MAX_RETMAX = 10_000

# Filters from the bucket README: restrict to articles present in the bucket.
IN_BUCKET_FILTER = "(open_access[Filter] OR author_manuscript[Filter])"
# PMC licence filters, keyed by the --licence choice of ingest_pmc.
LICENCE_FILTERS: dict[str, str] = {
    "any": "",
    "cc-by": "cc_by_license[Filter]",
    "cc0": "cc0_license[Filter]",
    "rewrite": (
        "(cc_by_license[Filter] OR cc0_license[Filter] OR cc_by-sa_license[Filter] "
        "OR cc_by-nc_license[Filter] OR cc_by-nc-sa_license[Filter])"
    ),
    "commercial": (
        "(cc0_license[Filter] OR cc_by_license[Filter] OR cc_by-sa_license[Filter] "
        "OR cc_by-nd_license[Filter])"
    ),
}


class EsearchError(RuntimeError):
    """Raised when ESearch returns an error or an unexpected document."""


@dataclass(frozen=True, slots=True)
class EsearchResult:
    """One page of ESearch results.

    Attributes:
        count: Total number of matches.
        pmcids: PMC IDs on this page, with the ``PMC`` prefix, in ESearch order.
    """

    count: int
    pmcids: tuple[str, ...]


def build_term(query: str, *, licence: str = "any") -> str:
    """Combine a user query with the in-bucket and licence filters.

    Args:
        query: An Entrez query, e.g. ``hypertension AND 2024[pdat]``; may be
            empty.
        licence: A key of :data:`LICENCE_FILTERS`.

    Returns:
        The full ESearch term.

    Raises:
        ValueError: For an unknown licence filter.
    """
    if licence not in LICENCE_FILTERS:
        raise ValueError(
            f"unknown licence filter {licence!r}; choose from {sorted(LICENCE_FILTERS)}"
        )
    parts = [
        f"({query.strip()})" if query.strip() else "",
        IN_BUCKET_FILTER,
        LICENCE_FILTERS[licence],
    ]
    return " AND ".join(part for part in parts if part)


def esearch_url(term: str, *, retmax: int, retstart: int = 0, api_key: str | None = None) -> str:
    """Build an ESearch URL for the PMC database.

    Args:
        term: The full search term.
        retmax: Page size (at most :data:`MAX_RETMAX`).
        retstart: Offset of the first result.
        api_key: Optional NCBI API key.

    Returns:
        The URL.
    """
    params: dict[str, str | int] = {
        "db": "pmc",
        "term": term,
        "retmode": "json",
        "retmax": min(retmax, MAX_RETMAX),
        "retstart": retstart,
        "sort": "pub_date",
        "tool": TOOL_NAME,
    }
    if api_key:
        params["api_key"] = api_key
    return f"{ESEARCH_URL}?{urlencode(params)}"


def parse_esearch(data: bytes) -> EsearchResult:
    """Parse an ESearch JSON response for the PMC database.

    Args:
        data: The response body.

    Returns:
        The count and the PMC IDs (ESearch returns bare numbers for PMC).

    Raises:
        EsearchError: If the response reports an error or is malformed.
    """
    try:
        document = json.loads(data)
        result = document["esearchresult"]
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError, TypeError) as exc:
        raise EsearchError(f"unexpected ESearch response: {exc}") from exc
    if "ERROR" in result:
        raise EsearchError(f"ESearch error: {result['ERROR']}")
    try:
        count = int(result["count"])
        ids = [str(item).strip() for item in result["idlist"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise EsearchError(f"unexpected ESearch result: {exc}") from exc
    if not all(item.isdigit() for item in ids):
        raise EsearchError("ESearch returned a non-numeric PMC ID")
    return EsearchResult(count=count, pmcids=tuple(f"PMC{item}" for item in ids))


def search_pmc(
    fetcher: PoliteFetcher,
    term: str,
    *,
    limit: int,
    api_key: str | None = None,
) -> list[str]:
    """Return up to ``limit`` PMC IDs matching a term, paging as needed.

    Args:
        fetcher: The polite fetcher.
        term: The full search term (see :func:`build_term`).
        limit: Maximum number of IDs.
        api_key: Optional NCBI API key.

    Returns:
        PMC IDs in ESearch order, without duplicates.

    Raises:
        EsearchError: If ESearch reports an error.
        rbcore.http.FetchError: If a request fails (with the API key redacted).
    """
    found: list[str] = []
    seen: set[str] = set()
    retstart = 0
    while len(found) < limit:
        # Results change daily, so pages are never served from the cache.
        page_size = min(limit - len(found), MAX_RETMAX)
        url = esearch_url(term, retmax=page_size, retstart=retstart, api_key=api_key)
        page = parse_esearch(_get_redacted(fetcher, url, api_key))
        for pmcid in page.pmcids:
            if pmcid not in seen:
                seen.add(pmcid)
                found.append(pmcid)
        retstart += len(page.pmcids)
        if not page.pmcids or retstart >= page.count:
            break
    return found[:limit]


def _get_redacted(fetcher: PoliteFetcher, url: str, api_key: str | None) -> bytes:
    """Fetch an ESearch URL without caching, keeping the API key out of any error.

    Args:
        fetcher: The polite fetcher.
        url: The ESearch URL (it may contain ``api_key``).
        api_key: The key to redact, if one was sent.

    Returns:
        The response body.

    Raises:
        rbcore.http.FetchError: If the request fails. The message has the key
            replaced by :data:`REDACTED`, and the original exception is not
            chained, because its message (and its cause's) carries the URL.
    """
    try:
        return fetcher.get(url, use_cache=False)
    except FetchError as exc:
        if not api_key:
            raise
        raise FetchError(str(exc).replace(api_key, REDACTED)) from None
