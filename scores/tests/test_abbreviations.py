"""Tests for the Schwartz-Hearst abbreviation algorithm."""

from __future__ import annotations

import pytest

from rbscores.burden.abbreviations import Abbreviation, find_abbreviations


def _pairs(sentence: str) -> list[tuple[str, str]]:
    """Return (short form, long form) pairs found in a sentence."""
    return [(a.short_form, a.long_form) for a in find_abbreviations(sentence)]


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        # Examples of the kind given by Schwartz and Hearst (2003).
        ("We measured body mass index (BMI) in all adults.", [("BMI", "body mass index")]),
        (
            "Heat shock transcription factor (HSF) binds DNA.",
            [("HSF", "Heat shock transcription factor")],
        ),
        ("The protein kinase C (PKC) pathway was active.", [("PKC", "protein kinase C")]),
        # Characters of the SF may sit inside words, but the first starts one.
        ("We used adenosine di-phosphate (ADP) here.", [("ADP", "adenosine di-phosphate")]),
        # Text after ", " or "; " inside the parenthesis is ignored.
        (
            "Magnetic resonance imaging (MRI, 3 T) was used.",
            [("MRI", "Magnetic resonance imaging")],
        ),
        # "SF (long form)" when the parenthetical has more than two words.
        ("Levels of TNF (tumour necrosis factor) rose.", [("TNF", "tumour necrosis factor")]),
        # ... or two words that are not a valid short form (too many letters).
        (
            "Newly added monomers are bound to the nucleotide ATP (adenosine triphosphate).",
            [("ATP", "adenosine triphosphate")],
        ),
        # Lower-case short forms explained by word initials are still found.
        ("A gap of 200 base pairs (bp) was seen.", [("bp", "base pairs")]),
        ("Fragments of 5 kilobases (kb) were cut.", [("kb", "kilobases")]),
    ],
)
def test_finds_definitions(sentence: str, expected: list[tuple[str, str]]) -> None:
    """Both orders of definition are found, with the shortest matching long form."""
    assert _pairs(sentence) == expected


@pytest.mark.parametrize(
    "sentence",
    [
        "Patients improved (p < 0.05) overall.",  # no letter-matching long form
        "The cohort was large (n = 120).",
        "Results are shown (Figure 2).",  # three characters only, but no match
        "We tested the drug (X).",  # one-character short form
        "Levels of tnf (tumour necrosis factor) rose.",  # SF before parens needs a capital
        "Rates of colon cancer (CRC) fell.",  # C, R, C cannot all be matched in order
        # A capitalised ordinary word is not an abbreviation ("SF (long form)" order).
        "Best (but the results were inconsistent) tried it.",
        "Pavlov (Pavlovian conditioning theory) described it.",
        # A lower-case word whose letters are scattered through the text before
        # it is not a short form ("long form (SF)" order needs word initials).
        "Apoptosis was increased in hepatocytes (inset).",
    ],
)
def test_rejects_non_definitions(sentence: str) -> None:
    """Statistics, figure references and unmatched pairs give nothing."""
    assert _pairs(sentence) == []


def test_long_form_word_limit() -> None:
    """A long form longer than min(|SF| + 5, 2 x |SF|) words is rejected."""
    # Two-letter SF: at most four words; "a b c d e f" style long forms fail.
    assert _pairs("We saw the very long list of many varied items called things (LT).") == []
    assert _pairs("We used liquid transfer (LT).") == [("LT", "liquid transfer")]


def test_offsets_point_at_the_forms() -> None:
    """Reported offsets (plus the sentence offset) index the original text."""
    paragraph = "Intro sentence. We measured body mass index (BMI) daily."
    sentence_start = paragraph.index("We")
    (found,) = find_abbreviations(paragraph[sentence_start:], offset=sentence_start)
    assert found == Abbreviation(
        "BMI", "body mass index", paragraph.index("BMI"), paragraph.index("body")
    )
    assert paragraph[found.short_start : found.short_end] == "BMI"
    assert paragraph[found.long_start : found.long_end] == "body mass index"


def test_multiple_and_nested_parentheses() -> None:
    """Every parenthetical in a sentence is considered; nesting is handled."""
    sentence = "Both interleukin 6 (IL6) and tumour necrosis factor (TNF (alpha)) rose."
    assert _pairs(sentence) == [("IL6", "interleukin 6")]
    # Every letter and digit of the short form must be matched.
    assert _pairs("Both interleukin six (IL6) rose.") == []
    assert _pairs("A sentence with an unclosed (parenthesis") == []
