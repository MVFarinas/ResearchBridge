"""Recognise and normalise scholarly identifiers typed or pasted by a reader.

The lookup flow (decisions.md §1.5, entry point 2) accepts a DOI, a PMC ID, a
PubMed ID, an arXiv ID or a title, in the forms people actually paste: bare
IDs, prefixed IDs (``doi:``, ``PMID:``, ``arXiv:``) and resolver or landing
page URLs. Anything else is treated as a title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal
from urllib.parse import unquote

IdentifierKind = Literal["doi", "pmcid", "pmid", "arxiv", "title"]

MIN_TITLE_LENGTH = 3
MAX_QUERY_LENGTH = 500

_DOI = re.compile(r"(10\.\d{4,9}/\S+)", re.IGNORECASE)
_DOI_PREFIXES = ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/")
_PMCID = re.compile(r"^(?:pmcid:\s*)?(PMC\d+)$", re.IGNORECASE)
_PMC_URL = re.compile(r"/(?:pmc/)?articles/(PMC\d+)", re.IGNORECASE)
_PMID = re.compile(r"^(?:pmid:\s*)?(\d{1,9})$", re.IGNORECASE)
_PUBMED_URL = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d{1,9})", re.IGNORECASE)
_ARXIV_NEW = r"\d{4}\.\d{4,5}"
_ARXIV_OLD = r"[a-z][a-z\-]+(?:\.[A-Z]{2})?/\d{7}"
_ARXIV = re.compile(rf"^(?:arxiv:\s*)?({_ARXIV_NEW}|{_ARXIV_OLD})(?:v\d+)?$", re.IGNORECASE)
_ARXIV_URL = re.compile(
    rf"arxiv\.org/(?:abs|pdf|html)/({_ARXIV_NEW}|{_ARXIV_OLD})(?:v\d+)?", re.IGNORECASE
)
_SPACES = re.compile(r"\s+")


class IdentifierError(ValueError):
    """Raised when a lookup query is empty, too short or too long."""


@dataclass(frozen=True, slots=True)
class ParsedIdentifier:
    """A recognised identifier, or a title.

    Attributes:
        kind: doi, pmcid, pmid, arxiv or title.
        value: The normalised value: a bare lower-case DOI, ``PMC<digits>``,
            digits, an arXiv ID without version, or the title text.
    """

    kind: IdentifierKind
    value: str


def normalise_doi(value: str | None) -> str | None:
    """Lower-case a DOI and strip any resolver prefix.

    Args:
        value: A DOI or DOI URL, or None.

    Returns:
        The bare, lower-cased DOI, or None.
    """
    if not value:
        return None
    text = value.strip()
    for prefix in (*_DOI_PREFIXES, "doi:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
    return text.strip().lower() or None


def parse_identifier(query: str) -> ParsedIdentifier:
    """Recognise what a reader typed.

    Args:
        query: The raw text.

    Returns:
        The identifier (or title) it denotes.

    Raises:
        IdentifierError: If the query is empty, shorter than
            :data:`MIN_TITLE_LENGTH` or longer than :data:`MAX_QUERY_LENGTH`.
    """
    text = _SPACES.sub(" ", query).strip()
    if len(text) > MAX_QUERY_LENGTH:
        raise IdentifierError(f"the query is longer than {MAX_QUERY_LENGTH} characters")
    if len(text) < MIN_TITLE_LENGTH and not text.isdigit():
        raise IdentifierError("enter a DOI, PMC ID, PubMed ID, arXiv ID or a title")

    # Identifiers inside URLs first (a PMC or arXiv URL may also contain a DOI-like path).
    for pattern, kind in ((_PMC_URL, "pmcid"), (_PUBMED_URL, "pmid"), (_ARXIV_URL, "arxiv")):
        if "/" in text and (match := pattern.search(text)):
            return _parsed(kind, match.group(1))

    # Bare or prefixed identifiers.
    if match := _PMCID.match(text):
        return ParsedIdentifier("pmcid", match.group(1).upper())
    if match := _PMID.match(text):
        return ParsedIdentifier("pmid", match.group(1).lstrip("0") or "0")
    if match := _ARXIV.match(text):
        return ParsedIdentifier("arxiv", match.group(1))
    if doi := _doi_in(text):
        return ParsedIdentifier("doi", doi)
    return ParsedIdentifier("title", text)


def _parsed(kind: str, value: str) -> ParsedIdentifier:
    """Build an identifier found in a URL.

    Args:
        kind: pmcid, pmid or arxiv.
        value: The captured value.

    Returns:
        The normalised identifier.
    """
    if kind == "pmcid":
        return ParsedIdentifier("pmcid", value.upper())
    if kind == "pmid":
        return ParsedIdentifier("pmid", value.lstrip("0") or "0")
    return ParsedIdentifier("arxiv", value)


def _doi_in(text: str) -> str | None:
    """Find a DOI in a bare, prefixed or URL form.

    Args:
        text: The query.

    Returns:
        The normalised DOI, or None.
    """
    candidate = normalise_doi(unquote(text))
    if candidate is None:
        return None
    match = _DOI.match(candidate)
    if match is None:
        return None
    # Trailing punctuation from a pasted sentence is not part of the DOI.
    return match.group(1).rstrip(".,;")
