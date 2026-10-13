"""Reference statistics for the composite, from training-split body text.

The composite z-scores each feature against fixed statistics
(:mod:`rbscores.readability.composite`). They come from *windows* of research
prose: the opening ~150 words (whole sentences) of each body section of
training-split articles, at most :data:`MAX_WINDOWS_PER_ARTICLE` per article.
Windows are about as long as an abstract or a lay summary, so their spread is
on the scale validation 1 compares. The training split is disjoint from the
validation split that validation 1 scores, and no lay summary is used, so the
calibration never sees which texts are "easy".
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Iterable, Sequence
from typing import Final

from spacy.language import Language

from rbscores.familiarity import Familiarity
from rbscores.readability.composite import FeatureReference, ReferenceStats
from rbscores.readability.features import FEATURE_NAMES, aggregate, sentence_stats
from rbscores.validation1.dataset import Article, detokenise

WINDOW_WORDS: Final = 150
MAX_WINDOWS_PER_ARTICLE: Final = 4
_MIN_UNITS: Final = 2

# The corpus ends each tokenised sentence with " ." (or " !", " ?").
_TOKENISED_SENTENCE_END = re.compile(r"(?<=\s[.!?])\s+")


def body_windows(
    article: Article,
    *,
    window_words: int = WINDOW_WORDS,
    max_windows: int = MAX_WINDOWS_PER_ARTICLE,
) -> list[str]:
    """Cut the opening window of whole sentences from each body section.

    Args:
        article: A training-split article.
        window_words: Stop adding sentences once a window has this many tokens.
        max_windows: At most this many windows per article.

    Returns:
        Detokenised windows, in section order. A section too short to fill a
        window is skipped.
    """
    windows: list[str] = []
    for section in article.body_sections:
        if len(windows) >= max_windows:
            break

        # Add whole sentences until the window is full.
        taken: list[str] = []
        count = 0
        for sentence in _TOKENISED_SENTENCE_END.split(section.strip()):
            taken.append(sentence)
            count += len(sentence.split())
            if count >= window_words:
                windows.append(detokenise(" ".join(taken)))
                break
    return windows


def compute_reference(
    texts: Sequence[str],
    *,
    nlp: Language,
    familiarity: Familiarity,
    version: str,
    description: str,
) -> ReferenceStats:
    """Compute per-feature means and SDs over a set of texts.

    Args:
        texts: The calibration units.
        nlp: spaCy pipeline with a parser.
        familiarity: Word-frequency source.
        version: Version string for the result.
        description: How the units were chosen.

    Returns:
        The reference statistics (sample SDs).

    Raises:
        ValueError: If fewer than two texts have words.
    """
    # Collect each feature's value for every text that has words.
    values: dict[str, list[float]] = {name: [] for name in FEATURE_NAMES}
    for doc in nlp.pipe(texts):
        features = aggregate(sentence_stats(doc, familiarity))
        if features is None:
            continue
        for name, value in features.values().items():
            values[name].append(value)

    # Means and sample SDs need at least two units.
    units = len(values[FEATURE_NAMES[0]])
    if units < _MIN_UNITS:
        raise ValueError(f"need at least {_MIN_UNITS} calibration texts with words, got {units}")
    return ReferenceStats(
        version=version,
        description=description,
        units=units,
        features={
            name: FeatureReference(
                mean=statistics.fmean(values[name]), sd=statistics.stdev(values[name])
            )
            for name in FEATURE_NAMES
        },
    )


def windows_for(articles: Iterable[Article]) -> list[str]:
    """Collect calibration windows from several articles.

    Args:
        articles: Training-split articles.

    Returns:
        All their windows, in order.
    """
    return [window for article in articles for window in body_windows(article)]
