"""A small OpenAlex client: single works by DOI or PMID, and keyword search.

OpenAlex data is CC0 (https://help.openalex.org/). Looking up one work by an
external ID is free; search is metered, so every answer is cached
(:mod:`rb_backend.metadata.cache`). ``OPENALEX_API_KEY`` is optional: without
it OpenAlex allows a small daily budget, and when it refuses a request the
caller degrades (search falls back to corpus-only results with a notice).

Licence fields OpenAlex reports are secondary signals only, never the gate
(decisions.md §1.1 addendum).

Why not pyalex (MIT): it fetches with ``requests`` outside
:class:`rbcore.http.PoliteFetcher` (so outside the shared rate limits, size
limits and User-Agent rule) and configures keys through global state; two
endpoints are a few lines over the fetcher we already have.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import quote, urlencode

from rb_backend.identifiers import normalise_doi
from rb_backend.metadata.fetch import get_json
from rb_backend.metadata.jsonvalues import (
    as_bool,
    as_float,
    as_int,
    as_list,
    as_mapping,
    as_str,
    year_counts,
)
from rbcore.http import PoliteFetcher

BASE_URL = "https://api.openalex.org"
SOURCE = "openalex"
# Fields of a work the reader uses (credibility panel and search results).
WORK_FIELDS = (
    "id",
    "doi",
    "ids",
    "display_name",
    "publication_year",
    "publication_date",
    "type",
    "cited_by_count",
    "counts_by_year",
    "fwci",
    "citation_normalized_percentile",
    "is_retracted",
    "primary_location",
    "best_oa_location",
    "authorships",
)
MAX_AUTHORS = 10
MAX_PER_PAGE = 25

WorkIdKind = Literal["doi", "pmid"]
SortOrder = Literal["relevance", "newest", "oldest"]
WorkType = Literal["article", "review", "preprint"]

_SORT_PARAMS: dict[str, str] = {
    "newest": "publication_date:desc",
    "oldest": "publication_date:asc",
}


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """One OpenAlex search.

    Attributes:
        query: Keywords.
        year_from: Earliest publication year, if any.
        year_to: Latest publication year, if any.
        work_types: Restrict to these work types (empty: any).
        sort: Relevance (OpenAlex's default) or by publication date.
        page: 1-based page number.
        per_page: Results per page (at most :data:`MAX_PER_PAGE`).
    """

    query: str
    year_from: int | None = None
    year_to: int | None = None
    work_types: tuple[WorkType, ...] = ()
    sort: SortOrder = "relevance"
    page: int = 1
    per_page: int = 10

    def canonical(self) -> str:
        """A canonical string for this request, used as its cache key.

        Returns:
            The query string the client sends, minus any API key.
        """
        return urlencode(self.params())

    def params(self) -> dict[str, str]:
        """The OpenAlex query parameters for this request.

        Returns:
            Parameters, without the API key.
        """
        params = {
            "search": self.query,
            "page": str(self.page),
            "per_page": str(min(self.per_page, MAX_PER_PAGE)),
            "select": ",".join(WORK_FIELDS),
        }
        filters = _filters(self)
        if filters:
            params["filter"] = filters
        if self.sort in _SORT_PARAMS:
            params["sort"] = _SORT_PARAMS[self.sort]
        return params


def _filters(request: SearchRequest) -> str:
    """The OpenAlex ``filter`` parameter for a search.

    Args:
        request: The search.

    Returns:
        Comma-separated filters, or "".
    """
    filters: list[str] = []
    # Year ranges use OpenAlex's "a-b", ">a-1" and "<b+1" forms.
    if request.year_from is not None and request.year_to is not None:
        filters.append(f"publication_year:{request.year_from}-{request.year_to}")
    elif request.year_from is not None:
        filters.append(f"publication_year:>{request.year_from - 1}")
    elif request.year_to is not None:
        filters.append(f"publication_year:<{request.year_to + 1}")
    if request.work_types:
        filters.append("type:" + "|".join(request.work_types))
    return ",".join(filters)


class OpenAlexClient:
    """Fetches OpenAlex works and searches through the polite fetcher."""

    def __init__(
        self, fetcher: PoliteFetcher, *, api_key: str | None = None, base_url: str = BASE_URL
    ) -> None:
        """Create the client.

        Args:
            fetcher: The polite fetcher.
            api_key: ``OPENALEX_API_KEY``, if set (sent as ``api_key``).
            base_url: API root (overridable for tests).
        """
        self._fetcher = fetcher
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    @property
    def has_key(self) -> bool:
        """Whether requests carry an API key."""
        return bool(self._api_key)

    def work_url(self, kind: WorkIdKind, value: str) -> str:
        """The URL of one work by an external ID (without the API key).

        Args:
            kind: "doi" or "pmid".
            value: The bare DOI or PMID.

        Returns:
            The URL.
        """
        params = urlencode({"select": ",".join(WORK_FIELDS)})
        return f"{self._base_url}/works/{kind}:{quote(value, safe='/')}?{params}"

    def search_url(self, request: SearchRequest) -> str:
        """The URL of a search (without the API key).

        Args:
            request: The search.

        Returns:
            The URL.
        """
        return f"{self._base_url}/works?{request.canonical()}"

    def work(self, kind: WorkIdKind, value: str) -> dict[str, Any] | None:
        """Fetch one work, trimmed to the fields the reader uses.

        Args:
            kind: "doi" or "pmid".
            value: The bare DOI or PMID.

        Returns:
            The trimmed work, or None if OpenAlex has no such work.

        Raises:
            rb_backend.metadata.errors.UpstreamRefusedError: If OpenAlex refuses.
            rb_backend.metadata.errors.UpstreamError: For other failures.
        """
        data = get_json(
            self._fetcher,
            self._keyed(self.work_url(kind, value)),
            source=SOURCE,
            secrets=[self._api_key],
        )
        return trim_work(data) if data is not None else None

    def search(self, request: SearchRequest) -> dict[str, Any]:
        """Run a search, trimmed to the fields the reader uses.

        Args:
            request: The search.

        Returns:
            ``{"count": int, "results": [trimmed works]}``.

        Raises:
            rb_backend.metadata.errors.UpstreamRefusedError: If OpenAlex refuses.
            rb_backend.metadata.errors.UpstreamError: For other failures.
        """
        data = get_json(
            self._fetcher,
            self._keyed(self.search_url(request)),
            source=SOURCE,
            secrets=[self._api_key],
        )
        meta = as_mapping(as_mapping(data).get("meta"))
        results = [trim_work(item) for item in as_list(as_mapping(data).get("results"))]
        return {"count": as_int(meta.get("count")) or 0, "results": results}

    def _keyed(self, url: str) -> str:
        """Add the API key to a URL when one is configured.

        Args:
            url: A URL that already has a query string.

        Returns:
            The URL to request.
        """
        if not self._api_key:
            return url
        return f"{url}&{urlencode({'api_key': self._api_key})}"


def trim_work(raw: object) -> dict[str, Any]:
    """Keep only the parts of a work the reader uses.

    Args:
        raw: A decoded OpenAlex work.

    Returns:
        The trimmed work (same field names as OpenAlex).
    """
    work = as_mapping(raw)
    trimmed = {field: work.get(field) for field in WORK_FIELDS if field in work}
    # Locations: only the licence, open-access flag and journal name are used.
    for field in ("primary_location", "best_oa_location"):
        location = as_mapping(work.get(field))
        trimmed[field] = {
            "license": location.get("license"),
            "is_oa": location.get("is_oa"),
            "source": {"display_name": as_mapping(location.get("source")).get("display_name")},
        }
    # Authors: names only, and only the first few.
    trimmed["authorships"] = [
        {"author": {"display_name": as_mapping(as_mapping(item).get("author")).get("display_name")}}
        for item in as_list(work.get("authorships"))[:MAX_AUTHORS]
    ]
    return trimmed


@dataclass(frozen=True, slots=True)
class OpenAlexWork:
    """A work as shown in search results.

    Attributes:
        openalex_id: The OpenAlex ID URL.
        doi: Bare, lower-cased DOI, if any.
        pmid: PubMed ID, if any.
        pmcid: PMC ID, if OpenAlex lists one.
        title: Title ("" if missing).
        publication_year: Year, if known.
        publication_date: ISO date ("" if unknown).
        work_type: OpenAlex type, e.g. "article".
        journal: Journal (primary location source) name.
        authors: Author names (first few).
        licence: The licence OpenAlex reports (secondary signal only).
        is_retracted: OpenAlex's retraction flag.
        cited_by_count: Citations OpenAlex counts.
    """

    openalex_id: str
    doi: str | None
    pmid: str | None
    pmcid: str | None
    title: str
    publication_year: int | None
    publication_date: str
    work_type: str
    journal: str
    authors: tuple[str, ...]
    licence: str | None
    is_retracted: bool
    cited_by_count: int | None


def parse_work(raw: object) -> OpenAlexWork:
    """Read a trimmed work into an :class:`OpenAlexWork`.

    Args:
        raw: A trimmed work.

    Returns:
        The work; missing or malformed fields become empty values.
    """
    work = as_mapping(raw)
    ids = as_mapping(work.get("ids"))
    primary = as_mapping(work.get("primary_location"))
    best = as_mapping(work.get("best_oa_location"))
    authors = tuple(
        name
        for item in as_list(work.get("authorships"))
        if (name := as_str(as_mapping(as_mapping(item).get("author")).get("display_name")))
    )
    return OpenAlexWork(
        openalex_id=as_str(work.get("id")) or "",
        doi=normalise_doi(as_str(work.get("doi")) or as_str(ids.get("doi"))),
        pmid=_last_path_segment(as_str(ids.get("pmid"))),
        pmcid=_pmcid(as_str(ids.get("pmcid"))),
        title=as_str(work.get("display_name")) or "",
        publication_year=as_int(work.get("publication_year")),
        publication_date=as_str(work.get("publication_date")) or "",
        work_type=as_str(work.get("type")) or "",
        journal=as_str(as_mapping(primary.get("source")).get("display_name")) or "",
        authors=authors,
        licence=as_str(primary.get("license")) or as_str(best.get("license")),
        is_retracted=as_bool(work.get("is_retracted")) is True,
        cited_by_count=as_int(work.get("cited_by_count")),
    )


@dataclass(frozen=True, slots=True)
class CitationMetrics:
    """Paper-level citation metrics from OpenAlex (decisions.md §2.3: neutral only).

    Attributes:
        cited_by_count: Citations OpenAlex counts.
        counts_by_year: ``[{"year", "count"}]`` ascending (about ten years).
        fwci: Field-weighted citation impact (1.0 = world average), if computed.
        citation_percentile: Percentile (0-100) among works of the same
            subfield, year and type, if computed.
        top_1_percent: Whether in the top 1% (None if not computed).
        top_10_percent: Whether in the top 10% (None if not computed).
        is_retracted: OpenAlex's flag (from the Retraction Watch database).
    """

    cited_by_count: int | None
    counts_by_year: list[dict[str, int]]
    fwci: float | None
    citation_percentile: float | None
    top_1_percent: bool | None
    top_10_percent: bool | None
    is_retracted: bool


def parse_metrics(raw: object) -> CitationMetrics:
    """Read the citation metrics of a trimmed work.

    Args:
        raw: A trimmed work.

    Returns:
        The metrics; absent values stay None.
    """
    work = as_mapping(raw)
    percentile = as_mapping(work.get("citation_normalized_percentile"))
    value = as_float(percentile.get("value"))
    pairs: dict[int, int] = {}
    for item in as_list(work.get("counts_by_year")):
        entry: Mapping[str, Any] = as_mapping(item)
        year, count = as_int(entry.get("year")), as_int(entry.get("cited_by_count"))
        if year is not None and count is not None:
            pairs[year] = count
    return CitationMetrics(
        cited_by_count=as_int(work.get("cited_by_count")),
        counts_by_year=year_counts(list(pairs.items())),
        fwci=as_float(work.get("fwci")),
        citation_percentile=round(value * 100, 1) if value is not None else None,
        top_1_percent=as_bool(percentile.get("is_in_top_1_percent")),
        top_10_percent=as_bool(percentile.get("is_in_top_10_percent")),
        is_retracted=as_bool(work.get("is_retracted")) is True,
    )


def _last_path_segment(url: str | None) -> str | None:
    """The last path segment of an identifier URL.

    Args:
        url: e.g. ``https://pubmed.ncbi.nlm.nih.gov/40173335``.

    Returns:
        ``40173335``, or None.
    """
    if not url:
        return None
    segment = url.rstrip("/").rsplit("/", 1)[-1]
    return segment or None


def _pmcid(url: str | None) -> str | None:
    """A PMC ID from an OpenAlex ``ids.pmcid`` value.

    Args:
        url: e.g. ``https://www.ncbi.nlm.nih.gov/pmc/articles/PMC123``.

    Returns:
        ``PMC123``, or None.
    """
    segment = _last_path_segment(url)
    if not segment:
        return None
    segment = segment.upper()
    if segment.isdigit():
        segment = f"PMC{segment}"
    return segment if segment.startswith("PMC") and segment[3:].isdigit() else None
