"""Nominalisation detection: nouns made from verbs or adjectives.

"The utilisation of" for "using", "an investigation of" for "investigating".
Detection is a suffix heuristic on nouns, the usual approach in readability
research when no derivational lexicon is available: a noun whose lemma ends in
one of :data:`NOMINAL_SUFFIXES` and is at least :data:`MIN_LENGTH` letters
long, minus a short stop list of common nouns that only look derived.

Known limits: it misses zero-derived nominalisations ("a change", "the
increase") and "-ing" gerunds, and it still counts some non-derived words that
are not in the stop list.
"""

from __future__ import annotations

from typing import Final

from spacy.tokens import Token

NOMINAL_SUFFIXES: Final = (
    "tion",
    "sion",
    "ment",
    "ness",
    "ity",
    "ance",
    "ence",
    "ancy",
    "ency",
)
"""Derivational suffixes that turn verbs or adjectives into nouns."""

MIN_LENGTH: Final = 7
"""Shorter nouns ("city", "nation", "dance") are almost never nominalisations."""

NOT_NOMINALISATIONS: Final = frozenset(
    {
        "audience",
        "cement",
        "community",
        "conscience",
        "element",
        "fragment",
        "garment",
        "instance",
        "pigment",
        "quality",
        "quantity",
        "science",
        "segment",
        "sentence",
        "society",
        "station",
        "university",
    }
)
"""Common nouns with a nominal suffix that are not derived from a verb or adjective."""


def is_nominalisation(token: Token) -> bool:
    """Decide whether a token is a nominalisation.

    Args:
        token: A tagged spaCy token.

    Returns:
        True for a common noun whose lemma has a nominal suffix, is long
        enough and is not in the stop list.
    """
    if token.pos_ != "NOUN" or not token.is_alpha:
        return False
    lemma = token.lemma_.lower()
    return (
        len(lemma) >= MIN_LENGTH
        and lemma.endswith(NOMINAL_SUFFIXES)
        and lemma not in NOT_NOMINALISATIONS
    )
