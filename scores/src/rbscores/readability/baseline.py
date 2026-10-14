"""Flesch-Kincaid grade level, as a comparison baseline only.

Not part of either ResearchBridge score: decisions.md §2.4 notes that reading-
grade formulas track lay readers' difficulty poorly. Validation 1 reports it
beside the composite so the composite can be judged against the familiar
formula.

Grade = 0.39 x (words / sentences) + 11.8 x (syllables / words) - 15.59
(Kincaid et al., 1975). Syllables are counted with a vowel-group heuristic,
so values differ slightly from tools that use a pronunciation dictionary.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_VOWEL_GROUPS = re.compile(r"[aeiouy]+")


def count_syllables(word: str) -> int:
    """Estimate the syllables in an English word.

    Counts vowel groups (``y`` included), drops a silent final "e" (but not
    "-le" as in "table"), and never returns less than 1 for a word with letters.

    Args:
        word: One word.

    Returns:
        Estimated syllables; 0 if the word has no letters.
    """
    letters = "".join(ch for ch in word.lower() if ch.isalpha())
    if not letters:
        return 0
    count = len(_VOWEL_GROUPS.findall(letters))
    if letters.endswith("e") and not letters.endswith("le") and count > 1:
        count -= 1
    return max(count, 1)


def flesch_kincaid_grade(sentences: Iterable[Iterable[str]]) -> float | None:
    """Compute the Flesch-Kincaid grade level.

    Args:
        sentences: Each sentence as its words (punctuation already removed).

    Returns:
        The grade level, or None if there are no words.
    """
    sentence_count = 0
    word_count = 0
    syllable_count = 0
    for sentence in sentences:
        words = [w for w in sentence if any(ch.isalnum() for ch in w)]
        if not words:
            continue
        sentence_count += 1
        word_count += len(words)
        syllable_count += sum(count_syllables(w) for w in words)
    if word_count == 0:
        return None
    return 0.39 * word_count / sentence_count + 11.8 * syllable_count / word_count - 15.59
