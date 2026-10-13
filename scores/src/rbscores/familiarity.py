"""Word familiarity: how likely a general reader is to know a word.

Familiarity is estimated from word frequency in general text, on the Zipf
scale (log10 of occurrences per billion words; 7 is "the", 3 is about one per
million, 0 is unseen). The default source is ``wordfreq`` 3.1.1: code under
Apache-2.0, frequency data under CC BY-SA 4.0 built from Wikipedia, subtitles
(OpenSubtitles 2018, SUBTLEX), news, Google Books, web text, Twitter and
Reddit. We only look values up from the unmodified, separately installed
package; we do not copy, modify or redistribute its word lists. Any word list
we ever derive from it and ship must itself be CC BY-SA 4.0 with attribution
(see docs/licence-inventory.md). The data is frozen (the author stopped
updating it in 2024), so newer terms look rarer than they are.

Two uses, kept distinct so the scores stay separable:

* :func:`jargon_band` reimplements the De-Jargonizer's three bands (Rakedzon
  et al., 2017, PLOS ONE 12(8): e0181742, CC BY): "common" words occur more than
  1,000 times in its 90-million-word BBC corpus, "rare" (jargon) fewer than 50
  times, "mid-frequency" in between. Converted to Zipf values, the cut-offs are
  about 4.05 and 2.74. The De-Jargonizer's code has no licence; only the
  published method is reimplemented here. Used by the readability score.
* :func:`unfamiliarity` maps a Zipf value to a weight in [0, 1] for the burden
  score: 0 at or above :data:`FAMILIAR_ZIPF`, rising linearly to 1 at or below
  :data:`UNKNOWN_ZIPF`. Both anchors are provisional choices, not fitted.
"""

from __future__ import annotations

import enum
import math
from typing import Final, Protocol

import wordfreq

_DEJARGONIZER_CORPUS_WORDS: Final = 90_000_000
"""Size of the De-Jargonizer's BBC corpus (Rakedzon et al., 2017)."""

JARGON_RARE_BELOW_ZIPF: Final = math.log10(50 / _DEJARGONIZER_CORPUS_WORDS * 1e9)
"""Zipf value of 50 occurrences in 90M words (about 2.74): below this, "rare"."""

JARGON_COMMON_ABOVE_ZIPF: Final = math.log10(1000 / _DEJARGONIZER_CORPUS_WORDS * 1e9)
"""Zipf value of 1,000 occurrences in 90M words (about 4.05): above this, "common"."""

FAMILIAR_ZIPF: Final = 4.0
"""Words at least this frequent (10 per million) carry no burden weight."""

UNKNOWN_ZIPF: Final = 1.5
"""Words at most this frequent (about 3 per 100 million) carry full burden weight."""

_MIN_LETTERS_IN_CODE: Final = 3
"""A letter-digit code (IL-6, COVID-19) is looked up by its letters only if it has this many."""


class Familiarity(Protocol):
    """Anything that can give the Zipf frequency of a word."""

    def zipf(self, word: str) -> float:
        """Return the word's Zipf frequency (0 when unseen).

        Args:
            word: A single word, any case.

        Returns:
            Zipf frequency, 0 or above.
        """
        ...


class WordfreqFamiliarity:
    """Familiarity from ``wordfreq``'s English data, with a per-instance cache."""

    def __init__(self, language: str = "en") -> None:
        """Create the lookup.

        Args:
            language: wordfreq language code.
        """
        self._language = language
        self._cache: dict[str, float] = {}

    def zipf(self, word: str) -> float:
        """Return the Zipf frequency of a word in general text.

        Codes that mix letters and digits (``IL-6``, ``PRC2``, ``COVID-19``)
        are not real words to wordfreq, which would split them and score the
        pieces; they are looked up by their letters when there are at least
        three (so ``COVID-19`` counts as "covid") and are otherwise unseen.

        Args:
            word: A single word, any case.

        Returns:
            Zipf frequency, 0 when unseen.
        """
        key = word.lower()
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # Reduce letter-digit codes to their letters, or treat them as unseen.
        lookup = key
        if any(ch.isdigit() for ch in key):
            letters = "".join(ch for ch in key if ch.isalpha())
            lookup = letters if len(letters) >= _MIN_LETTERS_IN_CODE else ""

        value = float(wordfreq.zipf_frequency(lookup, self._language)) if lookup else 0.0
        self._cache[key] = value
        return value


class JargonBand(enum.Enum):
    """The De-Jargonizer's three frequency bands."""

    COMMON = "common"
    MID = "mid"
    RARE = "rare"


def jargon_band(zipf: float) -> JargonBand:
    """Classify a Zipf frequency into a De-Jargonizer band.

    Args:
        zipf: Zipf frequency of a word form.

    Returns:
        COMMON above about 4.05, RARE below about 2.74, MID in between.
    """
    if zipf > JARGON_COMMON_ABOVE_ZIPF:
        return JargonBand.COMMON
    if zipf < JARGON_RARE_BELOW_ZIPF:
        return JargonBand.RARE
    return JargonBand.MID


def unfamiliarity(zipf: float) -> float:
    """Map a Zipf frequency to a burden weight in [0, 1].

    Args:
        zipf: Zipf frequency of a word.

    Returns:
        0 at or above :data:`FAMILIAR_ZIPF`, 1 at or below
        :data:`UNKNOWN_ZIPF`, linear in between.
    """
    span = FAMILIAR_ZIPF - UNKNOWN_ZIPF
    return min(1.0, max(0.0, (FAMILIAR_ZIPF - zipf) / span))
