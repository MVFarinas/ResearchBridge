"""Tests for in-text definition detection."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from spacy.language import Language

from rbscores.burden.definitions import DefinitionKind, find_definitions
from rbscores.familiarity import Familiarity

SyntheticFactory = Callable[..., Familiarity]

# Synthetic frequencies: these technical words are rare, everything else common.
RARE_WORDS = {
    "allostasis": 1.0,
    "autophagy": 1.0,
    "nestin": 1.0,
    "nephron": 1.0,
    "cytokine": 2.5,
    "pyrexia": 1.0,
    "apoptosis": 1.0,
    "zebrafish": 2.0,
    "il-6": 0.0,
    "bmi": 0.0,
}


@pytest.fixture
def familiarity(make_familiarity: SyntheticFactory) -> Familiarity:
    """Synthetic familiarity where :data:`RARE_WORDS` are rare."""
    return make_familiarity(RARE_WORDS)


def _defined(nlp: Language, familiarity: Familiarity, text: str) -> list[tuple[str, str]]:
    """Return (kind, term key) for each definition found in a text."""
    return [(str(d.kind), d.term_key) for d in find_definitions(nlp(text), familiarity)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("We measured body mass index (BMI) daily.", [("abbreviation", "bmi")]),
        ("Allostasis is defined as stability through change.", [("explicit", "allostasis")]),
        ("We define allostasis as stability through change.", [("explicit", "allostasis")]),
        ("Allostasis refers to stability through change.", [("explicit", "allostasis")]),
        ("Cells undergo a process known as autophagy.", [("naming", "autophagy")]),
        ("They found a protein called nestin in the brain.", [("naming", "nestin")]),
        ("The nephron is a structure that filters blood.", [("copular", "nephron")]),
        ("Patients had pyrexia (fever) for days.", [("gloss", "pyrexia")]),
        ("Programmed cell death (apoptosis) was common.", [("gloss", "apoptosis")]),
        ("Apoptosis, or programmed cell death, was assessed.", [("gloss", "apoptosis")]),
    ],
)
def test_definition_patterns(
    nlp: Language, familiarity: Familiarity, text: str, expected: list[tuple[str, str]]
) -> None:
    """Each pattern finds the defined term (and the gloss side is chosen correctly)."""
    assert _defined(nlp, familiarity, text) == expected


def test_appositive_with_determiner_defines_the_other_side(
    nlp: Language, familiarity: Familiarity
) -> None:
    """In "IL-6, a cytokine ..., ..." the term is IL-6, although "cytokine" is also rare."""
    found = find_definitions(
        nlp("IL-6, a cytokine involved in inflammation, was high."), familiarity
    )
    assert [(d.kind, d.term_key, d.gloss) for d in found] == [
        (DefinitionKind.APPOSITIVE, "il-6", "a cytokine involved in inflammation")
    ]


def test_relative_clause_copular(nlp: Language, familiarity: Familiarity) -> None:
    """A relative clause "X, which is a Y" defines X."""
    assert ("copular", "nephron") in _defined(
        nlp, familiarity, "Blood passes through the nephron, which is a tiny filter."
    )


@pytest.mark.parametrize(
    "text",
    [
        "Zebrafish grew quickly (n = 12).",
        "Zebrafish grew quickly (Fig. 2).",
        "Zebrafish grew quickly (Smith et al., 2019).",
        "The so-called nestin was absent.",
        "We studied mice, rats, or zebrafish in turn.",
    ],
)
def test_non_definitions(nlp: Language, familiarity: Familiarity, text: str) -> None:
    """Statistics, figure references, citations, "so-called" and list items define nothing."""
    assert _defined(nlp, familiarity, text) == []


def test_offsets_index_the_paragraph(nlp: Language, familiarity: Familiarity) -> None:
    """A definition's offsets point at the defined term in the text."""
    text = "First sentence here. Cells undergo a process known as autophagy."
    (definition,) = find_definitions(nlp(text), familiarity)
    assert text[definition.start : definition.end] == "autophagy"
