"""Tests for technical-term extraction."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from spacy.language import Language

from rbscores.burden.terms import (
    abbreviation_key,
    extract_terms,
    looks_like_abbreviation,
)
from rbscores.familiarity import Familiarity

SyntheticFactory = Callable[..., Familiarity]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("BMI", True),
        ("mRNA", True),
        ("IL-6", True),
        ("PRC2", True),
        ("5-HT", True),
        ("1A", False),
        ("Notch", False),
        ("protein", False),
        ("A", False),
        ("VERYLONGABBREVIATION", False),
    ],
)
def test_looks_like_abbreviation(text: str, expected: bool) -> None:
    """Two capitals, or a capital and a digit; panel labels and words are not abbreviations."""
    assert looks_like_abbreviation(text) is expected


def test_abbreviation_key_drops_plural_s() -> None:
    """Plural abbreviations share the singular's key."""
    assert abbreviation_key("SNPs") == "snp"
    assert abbreviation_key("SNP") == "snp"
    assert abbreviation_key("IL-6") == "il-6"
    assert abbreviation_key("Bus") == "bus"


def test_noun_phrase_core_starts_at_first_unfamiliar_word(
    nlp: Language, make_familiarity: SyntheticFactory
) -> None:
    """Familiar leading modifiers are dropped; familiar-only phrases give no term."""
    familiarity = make_familiarity({"randomized": 3.0})
    doc = nlp("A large randomized controlled trial tested the new method.")
    terms = extract_terms(doc, familiarity)
    assert [(t.text, t.key) for t in terms] == [
        ("randomized controlled trial", "randomized control trial")
    ]
    (term,) = terms
    assert doc.text[term.start : term.end] == "randomized controlled trial"
    assert term.weight == pytest.approx(0.4)
    assert term.word_weights[1:] == (0.0, 0.0)


def test_single_unfamiliar_words_outside_chunks(
    nlp: Language, make_familiarity: SyntheticFactory
) -> None:
    """Unfamiliar verbs and adjectives are terms on their own."""
    familiarity = make_familiarity({"cytotoxic": 2.0})
    terms = extract_terms(nlp("The drug was cytotoxic."), familiarity)
    assert [t.key for t in terms] == ["cytotoxic"]


def test_abbreviations_are_always_terms(nlp: Language, make_familiarity: SyntheticFactory) -> None:
    """An abbreviation is a term even when common (it then carries no weight)."""
    familiarity = make_familiarity({})
    terms = extract_terms(nlp("We sequenced DNA."), familiarity)
    assert [(t.key, t.abbreviation, t.weight) for t in terms] == [("dna", True, 0.0)]


def test_citations_and_figure_labels_are_not_terms(
    nlp: Language, make_familiarity: SyntheticFactory
) -> None:
    """Names in citations and panel labels are skipped."""
    familiarity = make_familiarity({"zebrafish": 2.0, "tilbeurgh": 0.0, "ent": 0.0})
    doc = nlp("Zebrafish grew (van den Ent et al., 2001; Tilbeurgh, 2003) as in Figure 1A.")
    assert [t.key for t in extract_terms(doc, familiarity)] == ["zebrafish"]


def test_core_is_cut_at_conjunctions_and_commas(
    nlp: Language, make_familiarity: SyntheticFactory
) -> None:
    """A mis-chunked "X or Y, an analog" does not become one term."""
    familiarity = make_familiarity({"amppnp": 0.0, "analog": 2.0})
    doc = nlp("We added ADP or AMPPNP, an analog of ATP, to the mix.")
    keys = [t.key for t in extract_terms(doc, familiarity)]
    assert "adp" in keys
    assert "amppnp" in keys
    assert not any(" " in k and "amppnp" in k for k in keys)


def test_real_frequencies_flag_jargon_not_everyday_words(
    nlp: Language, wordfreq_familiarity: Familiarity
) -> None:
    """With wordfreq data, "nephron" is a weighted term and "kidney" is not."""
    terms = extract_terms(
        nlp("Each kidney contains about a million nephrons."), wordfreq_familiarity
    )
    weights = {t.key: t.weight for t in terms}
    assert weights.get("nephron", 0) > 0.5
    assert "kidney" not in weights


def test_core_starts_after_a_determiner_and_needs_minimum_weight(
    nlp: Language, make_familiarity: SyntheticFactory
) -> None:
    """Nearly familiar words do not start terms, and a determiner cuts the core."""
    familiarity = make_familiarity({"consequently": 3.9, "paxillin": 1.0})
    doc = nlp("Consequently the paxillin absence was clear.")
    assert [t.key for t in extract_terms(doc, familiarity)] == ["paxillin absence"]
