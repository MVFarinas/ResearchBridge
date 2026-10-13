"""Tests for the burden score arithmetic, on hand-built synthetic term occurrences."""

from __future__ import annotations

import pytest

from rbscores.burden.definitions import Definition, DefinitionKind
from rbscores.burden.score import (
    EMPTY_DEFINITIONS,
    BurdenParams,
    DefinedTerms,
    LocatedTerm,
    TermLocation,
    compute_burden,
)
from rbscores.burden.terms import TermOccurrence


def _term(
    key: str, start: int, weights: tuple[float, ...], text: str | None = None
) -> TermOccurrence:
    """Build a synthetic occurrence whose words are the key's words."""
    words = tuple(key.split())
    return TermOccurrence(
        key=key,
        text=text or key,
        start=start,
        end=start + len(key),
        word_keys=words,
        word_zipfs=tuple(4.0 - 2.5 * w for w in weights),
        word_weights=weights,
    )


def _defined(*keys: str) -> DefinedTerms:
    """Build synthetic defined terms."""
    return DefinedTerms.from_definitions(
        ("p1", Definition(DefinitionKind.EXPLICIT, k, k, "synthetic gloss", 0, len(k)))
        for k in keys
    )


def test_terms_count_once_per_unit_and_sum_weights() -> None:
    """Repeated terms count once; burden is the weight total per 1,000 words."""
    terms = [
        LocatedTerm("p1", _term("apoptosis", 0, (0.4,))),
        LocatedTerm("p1", _term("nephron", 20, (1.0,))),
        LocatedTerm("p2", _term("apoptosis", 5, (0.4,))),
    ]
    result = compute_burden(terms, words=200, citations=0, defined=EMPTY_DEFINITIONS)
    assert result.burden_per_1000 == pytest.approx((0.4 + 1.0) * 1000 / 200)
    assert [(t.key, t.count) for t in result.undefined_terms] == [("nephron", 1), ("apoptosis", 2)]
    apoptosis = result.undefined_terms[1]
    assert apoptosis.locations == (TermLocation("p1", 0, 9), TermLocation("p2", 5, 14))


def test_defined_terms_are_removed_and_listed() -> None:
    """A defined term adds nothing and is reported as defined."""
    terms = [
        LocatedTerm("p1", _term("apoptosis", 0, (0.4,))),
        LocatedTerm("p1", _term("nephron", 20, (1.0,))),
    ]
    result = compute_burden(terms, words=100, citations=0, defined=_defined("nephron"))
    assert [t.key for t in result.undefined_terms] == ["apoptosis"]
    assert result.defined_terms == ("nephron",)
    assert result.burden_per_1000 == pytest.approx(4.0)


def test_defined_single_word_stops_counting_inside_longer_terms() -> None:
    """With "apoptosis" defined, "neuronal apoptosis" is weighted by "neuronal" only."""
    terms = [LocatedTerm("p1", _term("neuronal apoptosis", 0, (0.2, 0.8)))]
    result = compute_burden(terms, words=1000, citations=0, defined=_defined("apoptosis"))
    (term,) = result.undefined_terms
    assert term.weight == pytest.approx(0.2)
    fully = compute_burden(
        [LocatedTerm("p1", _term("cell apoptosis", 0, (0.0, 0.8)))],
        words=1000,
        citations=0,
        defined=_defined("apoptosis"),
    )
    assert fully.undefined_terms == ()
    assert fully.defined_terms == ("cell apoptosis",)


def test_definitions_can_be_switched_off() -> None:
    """The ablation keeps defined terms in the score."""
    terms = [LocatedTerm("p1", _term("nephron", 0, (1.0,)))]
    params = BurdenParams(use_definitions=False)
    result = compute_burden(
        terms, words=100, citations=0, defined=_defined("nephron"), params=params
    )
    assert result.burden_per_1000 == pytest.approx(10.0)
    assert result.defined_terms == ()


def test_citations_add_their_weight() -> None:
    """Each citation marker adds the citation weight, reported separately."""
    result = compute_burden([], words=500, citations=3, defined=EMPTY_DEFINITIONS)
    assert result.citation_burden_per_1000 == pytest.approx(3 * 0.5 * 2)
    assert result.term_burden_per_1000 == 0.0
    assert result.burden_per_1000 == result.citation_burden_per_1000
    custom = compute_burden(
        [],
        words=500,
        citations=3,
        defined=EMPTY_DEFINITIONS,
        params=BurdenParams(citation_weight=1.0),
    )
    assert custom.burden_per_1000 == pytest.approx(6.0)


def test_familiar_terms_add_nothing_and_ranking_breaks_ties_by_order() -> None:
    """Zero-weight terms are dropped; equal weights and counts keep first-seen order."""
    terms = [
        LocatedTerm("p1", _term("dna", 0, (0.0,))),
        LocatedTerm("p1", _term("zeta", 5, (0.5,))),
        LocatedTerm("p1", _term("alpha", 10, (0.5,))),
    ]
    result = compute_burden(terms, words=100, citations=0, defined=EMPTY_DEFINITIONS)
    assert [t.key for t in result.undefined_terms] == ["zeta", "alpha"]
    assert result.defined_terms == ()


def test_most_common_surface_form_is_reported() -> None:
    """The displayed text is the most frequent way the term is written."""
    terms = [
        LocatedTerm("p1", _term("snp", 0, (1.0,), text="SNPs")),
        LocatedTerm("p1", _term("snp", 9, (1.0,), text="SNP")),
        LocatedTerm("p1", _term("snp", 20, (1.0,), text="SNP")),
    ]
    (term,) = compute_burden(
        terms, words=10, citations=0, defined=EMPTY_DEFINITIONS
    ).undefined_terms
    assert term.text == "SNP"


def test_zero_words_gives_zero_burden() -> None:
    """An empty unit has no burden rather than dividing by zero."""
    assert (
        compute_burden([], words=0, citations=2, defined=EMPTY_DEFINITIONS).burden_per_1000 == 0.0
    )


def test_each_unfamiliar_word_counts_once_per_unit() -> None:
    """A rare word shared by several phrases adds its weight once; shorter terms go first."""
    terms = [
        LocatedTerm("p1", _term("paxillin homolog pxl1", 0, (1.0, 0.6, 1.0))),
        LocatedTerm("p1", _term("pxl1", 30, (1.0,))),
        LocatedTerm("p1", _term("pxl1 concentration", 40, (1.0, 0.0))),
    ]
    result = compute_burden(terms, words=1000, citations=0, defined=EMPTY_DEFINITIONS)
    # Equal weights and counts are listed in order of first appearance.
    assert [(t.key, t.weight) for t in result.undefined_terms] == [
        ("paxillin homolog pxl1", 1.0),
        ("pxl1", 1.0),
    ]
    assert result.burden_per_1000 == pytest.approx(2.0)
    assert result.defined_terms == ()
