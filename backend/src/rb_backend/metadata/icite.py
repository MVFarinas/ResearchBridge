"""A small NIH iCite client: citations by year and the Relative Citation Ratio.

iCite (https://icite.od.nih.gov/) covers PubMed-indexed papers and is in the
public domain. One request per PMID; the answer is trimmed to the fields the
credibility panel shows, with citing PMIDs aggregated into counts per year.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from rb_backend.metadata.fetch import get_json
from rb_backend.metadata.jsonvalues import (
    as_bool,
    as_float,
    as_int,
    as_list,
    as_mapping,
    year_counts,
)
from rbcore.http import PoliteFetcher

BASE_URL = "https://icite.od.nih.gov/api/pubs"
SOURCE = "icite"
FIELDS = (
    "pmid",
    "year",
    "citation_count",
    "relative_citation_ratio",
    "nih_percentile",
    "provisional",
    "is_research_article",
    "citedByPmidsByYear",
)


class ICiteClient:
    """Fetches iCite records through the polite fetcher."""

    def __init__(self, fetcher: PoliteFetcher, *, base_url: str = BASE_URL) -> None:
        """Create the client.

        Args:
            fetcher: The polite fetcher.
            base_url: API endpoint (overridable for tests).
        """
        self._fetcher = fetcher
        self._base_url = base_url

    def url(self, pmid: str) -> str:
        """The request URL for one PMID.

        Args:
            pmid: The PubMed ID.

        Returns:
            The URL.
        """
        return f"{self._base_url}?{urlencode({'pmids': pmid, 'fl': ','.join(FIELDS)})}"

    def pub(self, pmid: str) -> dict[str, Any] | None:
        """Fetch one paper's record, trimmed.

        Args:
            pmid: The PubMed ID.

        Returns:
            The trimmed record, or None if iCite has none.

        Raises:
            rb_backend.metadata.errors.UpstreamError: If the request fails.
        """
        data = get_json(self._fetcher, self.url(pmid), source=SOURCE)
        records = as_list(as_mapping(data).get("data"))
        if not records:
            return None
        return trim_pub(records[0])


def trim_pub(raw: object) -> dict[str, Any]:
    """Keep the fields used, with citing PMIDs counted per year.

    Args:
        raw: One record from iCite's ``data`` list.

    Returns:
        The trimmed record.
    """
    record = as_mapping(raw)
    # citedByPmidsByYear is a list of {"<citing pmid>": year} objects.
    years: Counter[int] = Counter()
    for item in as_list(record.get("citedByPmidsByYear")):
        for value in as_mapping(item).values():
            year = as_int(value)
            if year is not None:
                years[year] += 1
    return {
        "pmid": as_int(record.get("pmid")),
        "year": as_int(record.get("year")),
        "citation_count": as_int(record.get("citation_count")),
        "relative_citation_ratio": as_float(record.get("relative_citation_ratio")),
        "nih_percentile": as_float(record.get("nih_percentile")),
        "provisional": as_bool(record.get("provisional")),
        "is_research_article": as_bool(record.get("is_research_article")),
        "citations_by_year": year_counts(list(years.items())),
    }


@dataclass(frozen=True, slots=True)
class ICiteMetrics:
    """What the credibility panel shows from iCite.

    Attributes:
        citation_count: Citations in the NIH Open Citation Collection.
        citations_by_year: ``[{"year", "count"}]`` ascending.
        relative_citation_ratio: RCR (1.0 = median NIH-funded paper in the
            same field and year), if computed.
        rcr_provisional: Whether the RCR is provisional (recent papers).
        nih_percentile: Percentile of the RCR among NIH-funded papers.
        is_research_article: iCite's research-article flag (RCR is only
            meaningful for research articles).
    """

    citation_count: int | None
    citations_by_year: list[dict[str, int]]
    relative_citation_ratio: float | None
    rcr_provisional: bool | None
    nih_percentile: float | None
    is_research_article: bool | None


def parse_pub(trimmed: object) -> ICiteMetrics:
    """Read a trimmed iCite record.

    Args:
        trimmed: The output of :func:`trim_pub`.

    Returns:
        The metrics.
    """
    record = as_mapping(trimmed)
    by_year = [
        {"year": year, "count": count}
        for item in as_list(record.get("citations_by_year"))
        if (year := as_int(as_mapping(item).get("year"))) is not None
        and (count := as_int(as_mapping(item).get("count"))) is not None
    ]
    return ICiteMetrics(
        citation_count=as_int(record.get("citation_count")),
        citations_by_year=by_year,
        relative_citation_ratio=as_float(record.get("relative_citation_ratio")),
        rcr_provisional=as_bool(record.get("provisional")),
        nih_percentile=as_float(record.get("nih_percentile")),
        is_research_article=as_bool(record.get("is_research_article")),
    )
