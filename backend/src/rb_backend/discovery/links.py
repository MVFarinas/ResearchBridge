"""Outbound links: the canonical DOI and a Google Scholar search (decisions.md §1.5).

Google Scholar is only ever linked to, never fetched: it has no API and its
robots.txt disallows automated queries.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

SCHOLAR_SEARCH_URL = "https://scholar.google.com/scholar"


def doi_url(doi: str | None) -> str | None:
    """The resolver URL of a DOI (the publisher's canonical version).

    Args:
        doi: A bare DOI, or None.

    Returns:
        ``https://doi.org/<doi>``, or None.
    """
    if not doi:
        return None
    return "https://doi.org/" + quote(doi, safe="/()-._;:")


def scholar_search_url(*, title: str | None, doi: str | None) -> str | None:
    """A Google Scholar search URL for a paper (a link, never fetched).

    Args:
        title: The paper's title.
        doi: Its DOI (used when there is no title).

    Returns:
        The URL, or None when there is nothing to search for.
    """
    query = (title or "").strip() or (doi or "").strip()
    if not query:
        return None
    return f"{SCHOLAR_SEARCH_URL}?{urlencode({'q': query})}"
