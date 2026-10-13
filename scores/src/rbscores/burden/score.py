"""The PROVISIONAL prior-knowledge burden score (decisions.md §2.4).

Method, for one unit of text (paragraph, section or paper):

1. Take every candidate term in the unit (:mod:`rbscores.burden.terms`) and
   group occurrences by term key: a term the reader must know counts once
   per unit, however often it recurs.
2. Remove terms the document defines anywhere
   (:mod:`rbscores.burden.definitions`); a term defined in the abstract
   counts as defined throughout. A defined single word also stops counting
   inside longer terms: if "apoptosis" is defined, "neuronal apoptosis" is
   weighted by its other words.
3. Weight each remaining term by its unfamiliarity (0 to 1, the rarest
   word's weight).
4. Add each citation marker in the unit with weight
   :data:`DEFAULT_CITATION_WEIGHT` (an external result the text leans on).
5. Burden = (sum of term weights + citation weights) x 1000 / words.

Every weight here is a provisional choice, not fitted to human data. The
score is a population estimate: familiarity varies widely between readers,
even within one field (August et al.), so it says nothing certain about any
one reader.

Because terms count once per unit, longer units have proportionally fewer
new terms per word; compare units of similar length (validation 1 reports a
length-matched comparison for this reason).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Final

from rbscores.burden.definitions import Definition
from rbscores.burden.terms import TermOccurrence

DEFAULT_CITATION_WEIGHT: Final = 0.5
"""Provisional weight of one citation marker, against 1.0 for a wholly unknown term."""


@dataclass(frozen=True, slots=True)
class BurdenParams:
    """Tunable parts of the burden score.

    Attributes:
        citation_weight: Weight of one citation marker.
        use_definitions: Remove defined terms (False gives the ablation used
            in validation 1 to see whether definition detection matters).
    """

    citation_weight: float = DEFAULT_CITATION_WEIGHT
    use_definitions: bool = True


@dataclass(frozen=True, slots=True)
class TermLocation:
    """Where a term occurs.

    Attributes:
        paragraph_id: Stable paragraph ID.
        start: Character offset in the paragraph text.
        end: End offset (exclusive).
    """

    paragraph_id: str
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class LocatedTerm:
    """A term occurrence together with its paragraph.

    Attributes:
        paragraph_id: Stable paragraph ID.
        occurrence: The occurrence.
    """

    paragraph_id: str
    occurrence: TermOccurrence


@dataclass(frozen=True, slots=True)
class TermBurden:
    """An undefined, unfamiliar term and what it adds to the burden.

    Attributes:
        key: Normalised term key.
        text: The most common way it is written.
        weight: Unfamiliarity after removing defined words, 0 to 1.
        min_zipf: Zipf frequency of its rarest word.
        count: Occurrences in the unit.
        locations: Every occurrence, in document order.
        abbreviation: Whether it is a single abbreviation.
    """

    key: str
    text: str
    weight: float
    min_zipf: float
    count: int
    locations: tuple[TermLocation, ...]
    abbreviation: bool


@dataclass(frozen=True, slots=True)
class DefinedTerms:
    """The terms a document defines.

    Attributes:
        keys: Keys of every defined term.
        definitions: The definitions found, in document order, with the
            paragraph each one is in.
    """

    keys: frozenset[str]
    definitions: tuple[tuple[str, Definition], ...]

    @property
    def single_words(self) -> frozenset[str]:
        """Defined keys that are one word, which also stop counting inside longer terms."""
        return frozenset(k for k in self.keys if " " not in k)

    @classmethod
    def from_definitions(cls, located: Iterable[tuple[str, Definition]]) -> DefinedTerms:
        """Collect definitions found across paragraphs.

        Args:
            located: ``(paragraph_id, definition)`` pairs.

        Returns:
            The defined terms.
        """
        items = tuple(located)
        return cls(keys=frozenset(d.term_key for _, d in items), definitions=items)


EMPTY_DEFINITIONS: Final = DefinedTerms(keys=frozenset(), definitions=())


@dataclass(frozen=True, slots=True)
class BurdenResult:
    """The burden score of one unit.

    Attributes:
        words: Words in the unit.
        burden_per_1000: The PROVISIONAL burden score.
        term_burden_per_1000: The part from undefined terms.
        citation_burden_per_1000: The part from citation markers.
        citations: Citation markers in the unit.
        undefined_terms: Undefined, unfamiliar terms, most burdensome first.
        defined_terms: Keys of terms in the unit that would have counted but
            are defined in the document, sorted.
    """

    words: int
    burden_per_1000: float
    term_burden_per_1000: float
    citation_burden_per_1000: float
    citations: int
    undefined_terms: tuple[TermBurden, ...]
    defined_terms: tuple[str, ...]


def compute_burden(
    terms: Sequence[LocatedTerm],
    *,
    words: int,
    citations: int,
    defined: DefinedTerms,
    params: BurdenParams | None = None,
) -> BurdenResult:
    """Compute the burden score of one unit.

    Args:
        terms: Every term occurrence in the unit, in document order.
        words: Words in the unit (the per-1,000 denominator).
        citations: Citation markers in the unit.
        defined: Terms the whole document defines.
        params: Weights and switches; defaults to :class:`BurdenParams`.

    Returns:
        The score, with undefined terms ranked by weight, then count, then
        first position.
    """
    settings = params or BurdenParams()
    active = defined if settings.use_definitions else EMPTY_DEFINITIONS
    defined_words = active.single_words

    # Group occurrences by term key, keeping document order.
    by_key: dict[str, list[LocatedTerm]] = defaultdict(list)
    for located in terms:
        by_key[located.occurrence.key].append(located)

    # Weight each term, skipping defined terms and defined words inside terms.
    undefined: list[TermBurden] = []
    defined_used: set[str] = set()
    for key, group in by_key.items():
        weight = max(_effective_weight(g.occurrence, defined_words) for g in group)
        raw_weight = max(g.occurrence.weight for g in group)
        if key in active.keys or weight == 0.0:
            if raw_weight > 0.0:
                defined_used.add(key)
            continue
        undefined.append(_term_burden(key, group, weight))

    # Rank: heaviest first, then most frequent, then first to appear.
    first_seen = {key: index for index, key in enumerate(by_key)}
    undefined.sort(key=lambda t: (-t.weight, -t.count, first_seen[t.key]))

    term_total = sum(t.weight for t in undefined)
    citation_total = settings.citation_weight * citations
    scale = 1000.0 / words if words else 0.0
    return BurdenResult(
        words=words,
        burden_per_1000=(term_total + citation_total) * scale,
        term_burden_per_1000=term_total * scale,
        citation_burden_per_1000=citation_total * scale,
        citations=citations,
        undefined_terms=tuple(undefined),
        defined_terms=tuple(sorted(defined_used)),
    )


def _effective_weight(occurrence: TermOccurrence, defined_words: frozenset[str]) -> float:
    """Return a term's weight with defined words set to zero.

    Args:
        occurrence: A term occurrence.
        defined_words: Single-word keys the document defines.

    Returns:
        The largest weight among its words that are not defined.
    """
    return max(
        (
            w
            for k, w in zip(occurrence.word_keys, occurrence.word_weights, strict=True)
            if k not in defined_words
        ),
        default=0.0,
    )


def _term_burden(key: str, group: list[LocatedTerm], weight: float) -> TermBurden:
    """Summarise the occurrences of one term.

    Args:
        key: Term key.
        group: Its occurrences, in document order.
        weight: Its effective weight.

    Returns:
        The term's entry in the ranked list.
    """
    surface = Counter(g.occurrence.text for g in group).most_common(1)[0][0]
    return TermBurden(
        key=key,
        text=surface,
        weight=weight,
        min_zipf=min(min(g.occurrence.word_zipfs, default=0.0) for g in group),
        count=len(group),
        locations=tuple(
            TermLocation(g.paragraph_id, g.occurrence.start, g.occurrence.end) for g in group
        ),
        abbreviation=group[0].occurrence.abbreviation,
    )
