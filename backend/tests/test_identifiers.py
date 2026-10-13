"""Recognising what a reader typed into lookup (rb_backend.identifiers)."""

from __future__ import annotations

import pytest

from rb_backend.identifiers import (
    MAX_QUERY_LENGTH,
    IdentifierError,
    normalise_doi,
    parse_identifier,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.7554/eLife.93719", "10.7554/elife.93719"),
        ("https://doi.org/10.1/ABC", "10.1/abc"),
        ("doi:10.1/x", "10.1/x"),
        ("", None),
        (None, None),
    ],
)
def test_normalise_doi(value: str | None, expected: str | None) -> None:
    """DOIs are stored bare and lower-cased."""
    assert normalise_doi(value) == expected


@pytest.mark.parametrize(
    ("query", "kind", "value"),
    [
        ("10.1371/journal.pmed.1004542", "doi", "10.1371/journal.pmed.1004542"),
        ("https://doi.org/10.1371/JOURNAL.PMED.1004542", "doi", "10.1371/journal.pmed.1004542"),
        ("doi: 10.1016/S0140-6736(97)11096-0", "doi", "10.1016/s0140-6736(97)11096-0"),
        ("10.1101/2024.01.01.123456.", "doi", "10.1101/2024.01.01.123456"),
        (
            "https://doi.org/10.1016/S0140-6736%2897%2911096-0",
            "doi",
            "10.1016/s0140-6736(97)11096-0",
        ),
        ("PMC11964404", "pmcid", "PMC11964404"),
        ("pmc11964404", "pmcid", "PMC11964404"),
        ("https://pmc.ncbi.nlm.nih.gov/articles/PMC11964404/", "pmcid", "PMC11964404"),
        ("https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11964404", "pmcid", "PMC11964404"),
        ("40173335", "pmid", "40173335"),
        ("PMID: 40173335", "pmid", "40173335"),
        ("https://pubmed.ncbi.nlm.nih.gov/40173335/", "pmid", "40173335"),
        ("2310.06825", "arxiv", "2310.06825"),
        ("arXiv:2310.06825v2", "arxiv", "2310.06825"),
        ("https://arxiv.org/abs/2310.06825v1", "arxiv", "2310.06825"),
        ("hep-th/9901001", "arxiv", "hep-th/9901001"),
        (
            "  Predatory   journals: what can we do?  ",
            "title",
            "Predatory journals: what can we do?",
        ),
    ],
)
def test_parse_identifier(query: str, kind: str, value: str) -> None:
    """Bare, prefixed and URL forms are recognised and normalised; the rest is a title."""
    parsed = parse_identifier(query)
    assert (parsed.kind, parsed.value) == (kind, value)


@pytest.mark.parametrize("query", ["", "  ", "ab", "x" * (MAX_QUERY_LENGTH + 1)])
def test_unusable_queries_are_refused(query: str) -> None:
    """Empty, too short and too long queries raise IdentifierError."""
    with pytest.raises(IdentifierError):
        parse_identifier(query)
