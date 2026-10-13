"""Technical-term extraction: candidate noun phrases, abbreviations and rare words.

This is the term extraction shared with Phase 3's annotation targeting
(decisions.md §2.4 "build the term extraction once").

A term is found in three ways, over a spaCy-parsed paragraph:

1. **Noun-phrase terms.** For each noun chunk, the *term core* runs from the
   first word that is unfamiliar (burden weight at least
   :data:`MIN_TERM_WEIGHT`) or looks like an abbreviation, to the end of the
   chunk (its head). "A large randomized
   controlled trial" gives "randomized controlled trial"; "the new method"
   gives nothing, because every word is familiar. Only the part of the chunk
   after its last comma, bracket, conjunction or determiner is used, so a
   mis-chunked "ADP or AMPPNP, an analog" or "consequently the absence" does
   not become one term.
2. **Abbreviations** inside chunks are covered by (1), since an abbreviation
   starts a core.
3. **Single words** outside any core: unfamiliar verbs, adjectives, adverbs
   and nouns the chunker missed ("is cytotoxic", "phosphorylates").

Citation markers and figure or table references are skipped
(:mod:`rbscores.burden.references`). Named-entity recognition is deliberately
not used to skip names: spaCy's small model tags rare technical words as
people or places ("Pyrexia" as PERSON, "HeLa" as GPE), which would hide real
terms. An unusual name in running text therefore counts as a term.

A term's key normalises it for counting and for matching definitions: word
lemmas in lower case joined by spaces, with abbreviations lower-cased and a
plural "s" dropped ("SNPs" -> "snp"). The term's weight is the largest
unfamiliarity of its words (:func:`rbscores.familiarity.unfamiliarity`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from spacy.tokens import Doc, Span, Token

from rbscores.burden.references import excluded_spans, overlaps_any
from rbscores.familiarity import Familiarity, unfamiliarity

_CONTENT_POS: Final = frozenset({"NOUN", "PROPN", "VERB", "ADJ", "ADV"})
_NON_TERM_POS: Final = frozenset({"PRON", "DET", "PUNCT", "SYM", "NUM"})
_CORE_SEPARATORS: Final = frozenset({",", ";", ":", "(", ")", "[", "]"})
_ABBREVIATION_SHAPE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-/+.]{1,11}")
_MIN_ABBREVIATION_CAPITALS: Final = 2
_MIN_LETTERS_AFTER_DIGIT_START: Final = 2

MIN_TERM_WEIGHT: Final = 0.1
"""A word must be at least this unfamiliar (Zipf below about 3.75) to start a term.

Words just under the familiarity threshold ("consequently", "mortality") would
otherwise start terms with negligible weight and clutter the ranked list.
"""


@dataclass(frozen=True, slots=True)
class TermOccurrence:
    """One occurrence of a candidate technical term in a paragraph.

    Attributes:
        key: Normalised term key (see the module docstring).
        text: The term as written.
        start: Character offset of the term in the paragraph text.
        end: End offset (exclusive).
        word_keys: Normalised key of each word in the term.
        word_zipfs: Zipf frequency of each word.
        word_weights: Unfamiliarity weight of each word, 0 to 1.
        abbreviation: Whether the term is a single abbreviation.
    """

    key: str
    text: str
    start: int
    end: int
    word_keys: tuple[str, ...]
    word_zipfs: tuple[float, ...]
    word_weights: tuple[float, ...]
    abbreviation: bool = False

    @property
    def weight(self) -> float:
        """The term's unfamiliarity: the largest word weight."""
        return max(self.word_weights, default=0.0)


def looks_like_abbreviation(text: str) -> bool:
    """Decide whether a token looks like an abbreviation or code.

    Args:
        text: Token text.

    Returns:
        True for 2-12 characters of letters, digits and ``-/+.`` with at least
        two capitals ("BMI", "mRNA") or a capital and a digit ("IL-6", "PRC2").
        Something starting with a digit needs two letters ("5-HT"), so panel
        labels such as "1A" are not abbreviations.
    """
    if _ABBREVIATION_SHAPE.fullmatch(text) is None:
        return False
    letters = sum(1 for ch in text if ch.isalpha())
    if text[0].isdigit() and letters < _MIN_LETTERS_AFTER_DIGIT_START:
        return False
    capitals = sum(1 for ch in text if ch.isupper())
    has_digit = any(ch.isdigit() for ch in text)
    return capitals >= _MIN_ABBREVIATION_CAPITALS or (capitals >= 1 and has_digit)


def abbreviation_key(text: str) -> str:
    """Normalise an abbreviation for counting and matching.

    Args:
        text: Abbreviation as written ("SNPs", "IL-6").

    Returns:
        Lower-cased form with a plural "s" removed ("snp", "il-6").
    """
    stem = text[:-1] if text.endswith("s") and looks_like_abbreviation(text[:-1]) else text
    return stem.lower()


def word_key(token: Token) -> str:
    """Normalise one word for term keys.

    Args:
        token: A spaCy token.

    Returns:
        :func:`abbreviation_key` for abbreviations, else the lower-cased lemma.
    """
    if looks_like_abbreviation(token.text):
        return abbreviation_key(token.text)
    return token.lemma_.lower()


def word_zipf(token: Token, familiarity: Familiarity) -> float:
    """Return how frequent a word is in general text.

    Args:
        token: A spaCy token.
        familiarity: Word-frequency source.

    Returns:
        For abbreviations, the frequency of the singular form; otherwise the
        higher of the word form's and the lemma's frequency, so inflection
        does not make a common word look rare.
    """
    if looks_like_abbreviation(token.text):
        return familiarity.zipf(abbreviation_key(token.text))
    return max(familiarity.zipf(token.lower_), familiarity.zipf(token.lemma_.lower()))


def is_term_word(token: Token) -> bool:
    """Decide whether a token can be part of a term.

    Args:
        token: A spaCy token.

    Returns:
        True if it has a letter and is not a stop word, punctuation, pronoun,
        determiner, symbol or number.
    """
    return (
        any(ch.isalpha() for ch in token.text)
        and not token.is_stop
        and not token.is_punct
        and token.pos_ not in _NON_TERM_POS
    )


def _starts_term(token: Token, familiarity: Familiarity) -> bool:
    """Decide whether a word can start a term core.

    Args:
        token: A spaCy token.
        familiarity: Word-frequency source.

    Returns:
        True for a term word that is an abbreviation or has a burden weight of
        at least :data:`MIN_TERM_WEIGHT`.
    """
    if not is_term_word(token):
        return False
    if looks_like_abbreviation(token.text):
        return True
    return unfamiliarity(word_zipf(token, familiarity)) >= MIN_TERM_WEIGHT


def term_core(span: Span, familiarity: Familiarity) -> Span | None:
    """Return the technical core of a noun phrase.

    Args:
        span: A noun chunk (or any span ending at its head).
        familiarity: Word-frequency source.

    Returns:
        The span from the first term-starting word after the last separator
        (comma, bracket, colon, semicolon, conjunction or determiner) to the
        end, or None if no word there starts a term.
    """
    # Only the stretch after the last separator belongs to the phrase's head.
    begin = 0
    for index, token in enumerate(span):
        if token.text in _CORE_SEPARATORS or token.pos_ in {"CCONJ", "DET"}:
            begin = index + 1

    for index in range(begin, len(span)):
        if _starts_term(span[index], familiarity):
            return span[index:]
    return None


def occurrence_for(span: Span, familiarity: Familiarity) -> TermOccurrence | None:
    """Build a term occurrence from a span.

    Args:
        span: The term's tokens (a core from :func:`term_core` or one word).
        familiarity: Word-frequency source.

    Returns:
        The occurrence, or None if the span has no term words.
    """
    words = [t for t in span if is_term_word(t)]
    if not words:
        return None
    zipfs = tuple(word_zipf(t, familiarity) for t in words)
    return TermOccurrence(
        key=" ".join(word_key(t) for t in words),
        text=span.text,
        start=span.start_char,
        end=span.end_char,
        word_keys=tuple(word_key(t) for t in words),
        word_zipfs=zipfs,
        word_weights=tuple(unfamiliarity(z) for z in zipfs),
        abbreviation=len(words) == 1 and looks_like_abbreviation(words[0].text),
    )


def extract_terms(doc: Doc, familiarity: Familiarity) -> list[TermOccurrence]:
    """Extract candidate technical terms from a parsed paragraph.

    Args:
        doc: The paragraph, processed by a pipeline with a parser.
        familiarity: Word-frequency source.

    Returns:
        Term occurrences in document order. Terms whose words are all
        familiar are not returned; abbreviations always are. Nothing inside
        a citation marker or a figure or table reference is returned.
    """
    found: list[TermOccurrence] = []
    covered: set[int] = set()
    skip = excluded_spans(doc.text)

    # Noun-phrase terms (abbreviations included): the technical core of each chunk.
    for chunk in doc.noun_chunks:
        core = term_core(chunk, familiarity)
        occurrence = occurrence_for(core, familiarity) if core is not None else None
        if core is not None and occurrence is not None:
            found.append(occurrence)
            covered.update(range(core.start, core.end))

    # Single unfamiliar content words that no noun-phrase term covers.
    for token in doc:
        if token.i in covered or token.pos_ not in _CONTENT_POS:
            continue
        if _starts_term(token, familiarity):
            occurrence = occurrence_for(doc[token.i : token.i + 1], familiarity)
            if occurrence is not None:
                found.append(occurrence)

    kept = [o for o in found if not overlaps_any(o.start, o.end, skip)]
    kept.sort(key=lambda o: o.start)
    return kept
