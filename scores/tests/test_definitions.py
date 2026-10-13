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
        ("Allostasis means stability through change.", [("explicit", "allostasis")]),
        ("Allostasis denotes stability through change.", [("explicit", "allostasis")]),
        ("Allostasis stands for stability through change.", [("explicit", "allostasis")]),
        ("Cells undergo a process known as autophagy.", [("naming", "autophagy")]),
        ("Cells undergo a process termed autophagy.", [("naming", "autophagy")]),
        ("Cells undergo a process referred to as autophagy.", [("naming", "autophagy")]),
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


def test_misparsed_appositive_without_determiner_defines_nothing(
    nlp: Language, make_familiarity: SyntheticFactory
) -> None:
    """SpaCy tags "hepatocytes" as an appositive of "Apoptosis" here; that is not a definition."""
    familiarity = make_familiarity({"apoptosis": 1.0, "hepatocytes": 0.5, "hepatocyte": 0.5})
    text = "Apoptosis, or programmed cell death, removed damaged hepatocytes."
    assert _defined(nlp, familiarity, text) == [("gloss", "apoptosis")]


# Stock parentheticals, lists, names and misparses that real papers contain. Each
# was recorded as a definition before the fix and removed a real term from the
# burden score (review finding C-C1); real word frequencies are used, as there.
@pytest.mark.parametrize(
    "text",
    [
        "Apoptosis was increased in hepatocytes (data not shown).",
        "Apoptosis was increased in hepatocytes (unpublished observations).",
        "Apoptosis was increased in hepatocytes (arrows).",
        "Apoptosis was increased in hepatocytes (Methods).",
        "Apoptosis was increased in hepatocytes (two-tailed t-test).",
        "Apoptosis was increased in hepatocytes (wild type).",
        # Further figure and results idioms found in review round 2 (R-1).
        "Apoptosis was increased in hepatocytes (black arrowheads).",
        "Apoptosis was increased in hepatocytes (white arrows).",
        "Apoptosis was increased in hepatocytes (negative control).",
        "Apoptosis was increased in hepatocytes (vehicle).",
        "Apoptosis was increased in hepatocytes (log-rank test).",
        "Apoptosis was increased in hepatocytes (scale bar).",
        "Apoptosis was increased in hepatocytes (open circles).",
        "Apoptosis was increased in hepatocytes (filled circles).",
        "Apoptosis was increased in hepatocytes (error bars).",
        "Apoptosis was increased in hepatocytes (inset).",
        "Mice were sacrificed at the endpoint (day 7).",
        "It was published in the Lancet, Deutsches Ärzteblatt, The BMJ, and JAMA.",
        "Wei Mao (Université Paris-Saclay) is the first author.",
        "The filament could match the curvature of the liposome (resulting in a sensing role).",
        "He ran experiments on humans (he was a pioneer in the galvanic skin response).",
        "Paramecia learned where cathodal stimulation (which exerted an attraction) was applied.",
        "Gelber applies to Protozoa concepts (reinforcement and approach response) freely.",
        "Small stock ownership (EUR 5000) was declared.",
        "The results were inconsistent (Best, 1954; Mirsky and Katz, 1958).",
        "We focus on Pavlovian conditioning (Pavlov, 1927) here.",
        "Best (but the results were inconsistent) tried it.",
        "Adiposity is a major source of inflammaging.",
        "Synaptic plasticity is clearly not an option for protozoa.",
    ],
)
def test_stock_phrases_lists_and_names_define_nothing(
    nlp: Language, wordfreq_familiarity: Familiarity, text: str
) -> None:
    """Stock parentheticals, comma lists, names, clauses and citations are not definitions."""
    assert _defined(nlp, wordfreq_familiarity, text) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Nuclear material changes during conjugation (sexual reproduction) in ciliates.",
            [("gloss", "conjugation")],
        ),
        ("Levels of ATP (adenosine triphosphate) rose.", [("abbreviation", "atp")]),
        (
            "Infection by Naegleria fowleri, a free-living amoeba, is rare.",
            [("appositive", "naegleria fowleri")],
        ),
        # "median" outside a statistic, and a numbered name, are ordinary glosses (R-4).
        (
            "Carpal tunnel syndrome (compression of the median nerve) is common.",
            [("gloss", "carpal tunnel syndrome")],
        ),
        ("Down syndrome (trisomy 21) is common.", [("gloss", "trisomy")]),
        ("Trisomy 21 (Down syndrome) is common.", [("gloss", "trisomy")]),
    ],
)
def test_real_definitions_survive_the_filters(
    nlp: Language,
    wordfreq_familiarity: Familiarity,
    text: str,
    expected: list[tuple[str, str]],
) -> None:
    """The stricter checks still accept ordinary glosses, abbreviations and appositives."""
    assert _defined(nlp, wordfreq_familiarity, text) == expected
