"""Readability features: how the prose itself is written (decisions.md §2.4).

Features are computed per sentence (:class:`SentenceStats`) and aggregated over
any set of sentences (:func:`aggregate`), so a paragraph, a section and a paper
are all scored the same way: by pooling their sentences, not by averaging
paragraph scores.

Five features, each oriented so that **higher means harder**:

* ``mean_sentence_length``: words per sentence. A word is any token containing
  a letter or digit (so numbers count; punctuation does not).
* ``mean_parse_depth``: mean over sentences of the dependency tree's depth (the
  root is depth 1), a measure of how deeply clauses and phrases nest.
* ``nominalisation_rate``: nominalisations per 100 words
  (:mod:`rbscores.readability.nominalisations`).
* ``passive_rate``: share of sentences with at least one passive clause
  (a ``nsubjpass``, ``csubjpass`` or ``auxpass`` dependency).
* ``jargon_density``: the De-Jargonizer measure, (rare + 0.5 x mid-frequency)
  / alphabetic words, with bands from :func:`rbscores.familiarity.jargon_band`
  looked up by word form. Every rare word counts, defined or not: this is
  about how the text is written. Whether the text explains its terms is the
  burden score's job.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Final

from spacy.tokens import Doc, Span, Token

from rbscores.familiarity import Familiarity, JargonBand, jargon_band
from rbscores.readability.nominalisations import is_nominalisation

FEATURE_NAMES: Final = (
    "mean_sentence_length",
    "mean_parse_depth",
    "nominalisation_rate",
    "passive_rate",
    "jargon_density",
)
"""The five readability features, in a fixed order."""

_PASSIVE_DEPS: Final = frozenset({"nsubjpass", "csubjpass", "auxpass"})
_NON_WORD_POS: Final = frozenset({"PUNCT", "SYM", "SPACE"})


@dataclass(frozen=True, slots=True)
class SentenceStats:
    """Counts for one sentence, the unit everything is aggregated from.

    Attributes:
        words: Word tokens (letters or digits).
        depth: Depth of the dependency tree (root = 1).
        passive: Whether the sentence has a passive clause.
        nominalisations: Nominalisations in the sentence.
        alphabetic_words: Alphabetic tokens, the jargon denominator.
        rare_words: Alphabetic tokens in the De-Jargonizer "rare" band.
        mid_words: Alphabetic tokens in the "mid-frequency" band.
    """

    words: int
    depth: int
    passive: bool
    nominalisations: int
    alphabetic_words: int
    rare_words: int
    mid_words: int


@dataclass(frozen=True, slots=True)
class ReadabilityFeatures:
    """The five readability features for one unit of text (higher = harder).

    Attributes:
        sentences: Sentences pooled.
        words: Words pooled.
        mean_sentence_length: Words per sentence.
        mean_parse_depth: Mean dependency-tree depth per sentence.
        nominalisation_rate: Nominalisations per 100 words.
        passive_rate: Share of sentences with a passive clause, 0 to 1.
        jargon_density: (rare + 0.5 x mid) / alphabetic words, 0 to 1.
    """

    sentences: int
    words: int
    mean_sentence_length: float
    mean_parse_depth: float
    nominalisation_rate: float
    passive_rate: float
    jargon_density: float

    def values(self) -> dict[str, float]:
        """Return the five feature values keyed by :data:`FEATURE_NAMES`.

        Returns:
            Feature name to value.
        """
        return {name: float(getattr(self, name)) for name in FEATURE_NAMES}

    def as_dict(self) -> dict[str, float | int]:
        """Return every field, for JSON output.

        Returns:
            Field name to value.
        """
        return asdict(self)


def is_word(token: Token) -> bool:
    """Decide whether a token counts as a word.

    Args:
        token: A spaCy token.

    Returns:
        True if it contains a letter or digit and is not punctuation, a
        symbol or whitespace.
    """
    return (
        not token.is_space
        and token.pos_ not in _NON_WORD_POS
        and any(ch.isalnum() for ch in token.text)
    )


def parse_depth(sentence: Span) -> int:
    """Return the depth of a sentence's dependency tree.

    Args:
        sentence: A parsed sentence span.

    Returns:
        The largest number of tokens on a path from the root to a word
        (root = 1); 0 for a sentence without words.
    """
    depths: dict[int, int] = {}
    for token in sentence:
        # Walk up to the first token whose depth is known, remembering the path.
        path: list[Token] = []
        node = token
        while node.i not in depths:
            path.append(node)
            head = node.head
            if head.i == node.i or not sentence.start <= head.i < sentence.end:
                depths[node.i] = 1
                path.pop()
                break
            node = head

        # Assign depths back down the path.
        depth = depths[node.i]
        for step in reversed(path):
            depth += 1
            depths[step.i] = depth

    return max((depths[t.i] for t in sentence if is_word(t)), default=0)


def sentence_stats(doc: Doc, familiarity: Familiarity) -> list[SentenceStats]:
    """Compute per-sentence counts for a parsed document.

    Args:
        doc: A spaCy ``Doc`` processed by a pipeline with a parser.
        familiarity: Word-frequency source for the jargon bands.

    Returns:
        One entry per sentence that has at least one word.
    """
    stats: list[SentenceStats] = []
    for sentence in doc.sents:
        words = [t for t in sentence if is_word(t)]
        if not words:
            continue

        # Jargon bands are looked up by word form, as in the De-Jargonizer.
        alphabetic = [t for t in words if t.is_alpha]
        bands = [jargon_band(familiarity.zipf(t.lower_)) for t in alphabetic]

        stats.append(
            SentenceStats(
                words=len(words),
                depth=parse_depth(sentence),
                passive=any(t.dep_ in _PASSIVE_DEPS for t in sentence),
                nominalisations=sum(1 for t in words if is_nominalisation(t)),
                alphabetic_words=len(alphabetic),
                rare_words=bands.count(JargonBand.RARE),
                mid_words=bands.count(JargonBand.MID),
            )
        )
    return stats


def aggregate(stats: Sequence[SentenceStats]) -> ReadabilityFeatures | None:
    """Pool sentence counts into the five features.

    Args:
        stats: Sentences of the unit (any order).

    Returns:
        The features, or None if the unit has no words.
    """
    sentences = len(stats)
    words = sum(s.words for s in stats)
    if sentences == 0 or words == 0:
        return None

    alphabetic = sum(s.alphabetic_words for s in stats)
    jargon = sum(s.rare_words + 0.5 * s.mid_words for s in stats)
    return ReadabilityFeatures(
        sentences=sentences,
        words=words,
        mean_sentence_length=words / sentences,
        mean_parse_depth=sum(s.depth for s in stats) / sentences,
        nominalisation_rate=100.0 * sum(s.nominalisations for s in stats) / words,
        passive_rate=sum(1 for s in stats if s.passive) / sentences,
        jargon_density=jargon / alphabetic if alphabetic else 0.0,
    )
