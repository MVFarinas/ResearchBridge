"""In-text definitions: terms the text itself explains (decisions.md §2.4).

A term the text defines is no burden on the reader, so the burden score
removes it. Six kinds of definition are detected over a spaCy-parsed
paragraph:

* ``abbreviation``: Schwartz-Hearst pairs, "body mass index (BMI)"
  (:mod:`rbscores.burden.abbreviations`). The short form is defined; the long
  form stays a term in its own right.
* ``explicit``: "X is defined as ...", "we define X as ...", "X refers to
  ...", "X means ...", "X stands for ...".
* ``naming``: "... known as X", "... called X", "... termed X", "... referred
  to as X" (but not "so-called X", which flags a term without explaining it).
* ``copular``: "X is a Y that/which/of/in ..." (an indefinite noun with a
  modifier), and "X, which is a Y".
* ``appositive``: "X, a Y that ..., ..." (spaCy's ``appos`` relation).
* ``gloss``: "X (Y)", "X (i.e., Y)" and "X, or Y,".

For appositives and glosses either side may be the term ("IL-6 (a cytokine)"
versus "programmed cell death (apoptosis)"). For an appositive, the side that
starts with a determiner ("a cytokine", "the protein") is the explanation and
the other side the term; an appositive with a determiner on neither or both
sides is ignored, because spaCy's small model often mislabels plain noun
phrases as appositives (parenthetical ones are handled as glosses). For a
gloss, the side with the less familiar words is taken as the defined term and
the other as its explanation; if neither is less familiar, no definition is
recorded. An explanation must contain a word
of three or more letters and must not be a citation, a figure or table
reference, or a statistic.

These are heuristics with known misses (definitions spread across sentences,
dashes, figures) and false hits (a copular sentence that classifies rather
than explains). Their recall and precision have not been measured yet.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Final

from spacy.tokens import Doc, Span, Token

from rbscores.burden.abbreviations import Abbreviation, find_abbreviations
from rbscores.burden.references import excluded_spans, overlaps_any
from rbscores.burden.terms import (
    abbreviation_key,
    is_term_word,
    occurrence_for,
    term_core,
    word_zipf,
)
from rbscores.familiarity import Familiarity, unfamiliarity

_RELATIVE_PRONOUNS: Final = frozenset({"which", "that", "who"})
_NAMING_DIRECT: Final = frozenset({"called", "termed", "named", "dubbed"})
_NAMING_WITH_AS: Final = frozenset({"known", "referred", "designated"})
_GLOSS_LEAD_INS: Final = frozenset({"i.e.", "i.e", "ie", "that", "is", "or", ",", "also"})
_NOT_GLOSS_STARTS: Final = frozenset(
    {
        "fig",
        "fig.",
        "figs",
        "figs.",
        "figure",
        "figures",
        "table",
        "tables",
        "supplementary",
        "see",
        "e.g.",
        "eg",
        "ref",
        "refs",
        "panel",
        "appendix",
        "box",
        "equation",
        "eq",
        "eq.",
    }
)
_NOT_GLOSS_CHARS: Final = frozenset("=<>±%")
_MAX_GLOSS_TOKENS: Final = 25
_MAX_OR_GLOSS_TOKENS: Final = 8
_MIN_GLOSS_WORD_LETTERS: Final = 3
_LIST_SEPARATORS: Final = frozenset({",", ";"})
_GLOSS_END: Final = frozenset({",", ")", ".", ";", "\u2013", "\u2014"})


class DefinitionKind(enum.StrEnum):
    """How a definition was recognised."""

    ABBREVIATION = "abbreviation"
    EXPLICIT = "explicit"
    NAMING = "naming"
    COPULAR = "copular"
    APPOSITIVE = "appositive"
    GLOSS = "gloss"


@dataclass(frozen=True, slots=True)
class Definition:
    """A term defined in the text.

    Attributes:
        kind: How it was recognised.
        term_key: Normalised key of the defined term (matches term keys).
        term_text: The defined term as written.
        gloss: The explanation (for abbreviations, the long form).
        start: Offset of the defined term in the paragraph text.
        end: End offset (exclusive).
    """

    kind: DefinitionKind
    term_key: str
    term_text: str
    gloss: str
    start: int
    end: int


class _Finder:
    """Runs every definition pattern over one parsed paragraph."""

    def __init__(self, doc: Doc, familiarity: Familiarity) -> None:
        """Index the paragraph's noun chunks.

        Args:
            doc: The parsed paragraph.
            familiarity: Word-frequency source.
        """
        self.doc = doc
        self.familiarity = familiarity
        self.chunks: dict[int, Span] = {
            index: chunk for chunk in doc.noun_chunks for index in range(chunk.start, chunk.end)
        }
        self.skip = excluded_spans(doc.text)
        self.found: list[Definition] = []

    def run(self) -> list[Definition]:
        """Apply every pattern.

        Returns:
            Definitions sorted by position, without duplicates.
        """
        abbreviations = self._abbreviations()
        covered = [
            (min(a.short_start, a.long_start), max(a.short_end, a.long_end)) for a in abbreviations
        ]
        for token in self.doc:
            self._naming(token)
            self._explicit(token)
            self._copular(token)
            self._appositive(token)
            self._or_gloss(token)
            if token.text == "(":
                self._parenthetical_gloss(token, covered)

        # Deduplicate: several patterns can find the same definition. The
        # first one found wins, so an abbreviation pair beats the appositive
        # spaCy also sees in "body mass index (BMI)".
        unique: dict[tuple[str, int], Definition] = {}
        for definition in self.found:
            unique.setdefault((definition.term_key, definition.start), definition)
        return sorted(unique.values(), key=lambda d: (d.start, d.term_key))

    # --- Patterns -----------------------------------------------------------

    def _abbreviations(self) -> list[Abbreviation]:
        """Record Schwartz-Hearst abbreviation definitions, sentence by sentence.

        Returns:
            The abbreviations found, so parenthetical glosses can skip them.
        """
        found: list[Abbreviation] = []
        for sentence in self.doc.sents:
            for abbreviation in find_abbreviations(sentence.text, offset=sentence.start_char):
                found.append(abbreviation)
                self.found.append(
                    Definition(
                        kind=DefinitionKind.ABBREVIATION,
                        term_key=abbreviation_key(abbreviation.short_form),
                        term_text=abbreviation.short_form,
                        gloss=abbreviation.long_form,
                        start=abbreviation.short_start,
                        end=abbreviation.short_end,
                    )
                )
        return found

    def _naming(self, token: Token) -> None:
        """Record "known as X", "called X", "termed X", "referred to as X".

        Args:
            token: Candidate naming verb.
        """
        doc = self.doc
        lower = token.lower_
        target: int | None = None
        if lower in _NAMING_DIRECT and not _after_so_hyphen(token):
            target = token.i + 1
        elif lower in _NAMING_WITH_AS:
            if _text_at(doc, token.i + 1) == "as":
                target = token.i + 2
            elif _text_at(doc, token.i + 1) == "to" and _text_at(doc, token.i + 2) == "as":
                target = token.i + 3
        if target is None or target >= len(doc):
            return

        # The named term is the phrase right after; the thing named is the gloss.
        gloss_span = self._phrase(token.head) if token.head.i != token.i else None
        gloss = gloss_span.text if gloss_span is not None else token.sent.text
        self._record(DefinitionKind.NAMING, self._phrase(doc[target]), gloss)

    def _explicit(self, token: Token) -> None:
        """Record "X is defined as", "we define X as", "X refers to", "X means", "X stands for".

        Args:
            token: Candidate defining verb.
        """
        lemma = token.lemma_.lower()
        children = list(token.children)
        subject: Token | None = None
        gloss_head: Token | None = None
        if lemma == "define":
            gloss_head = _child_with_text(children, "as")
            subject = _child_with_dep(children, "nsubjpass") or _child_with_dep(children, "dobj")
        elif lemma == "refer" and _child_with_dep(children, "auxpass") is None:
            gloss_head = _child_with_text(children, "to")
            subject = _child_with_dep(children, "nsubj")
        elif lemma in {"mean", "denote"} and token.tag_ in {"VBZ", "VBP"}:
            gloss_head = _child_with_dep(children, "dobj") or _child_with_dep(children, "ccomp")
            subject = _child_with_dep(children, "nsubj")
        elif lemma == "stand":
            gloss_head = _child_with_text(children, "for")
            subject = _child_with_dep(children, "nsubj")
        if subject is None or gloss_head is None:
            return
        subject = _resolve_relative(subject, token)
        self._record(DefinitionKind.EXPLICIT, self._phrase(subject), _subtree(gloss_head).text)

    def _copular(self, token: Token) -> None:
        """Record "X is a Y that ..." and "X, which is a Y".

        Args:
            token: Candidate copula.
        """
        if token.lemma_ != "be":
            return
        children = list(token.children)
        attribute = _child_with_dep(children, "attr")
        subject = _child_with_dep(children, "nsubj")
        if attribute is None or subject is None or attribute.pos_ not in {"NOUN", "PROPN"}:
            return
        if not any(c.dep_ == "det" and c.lower_ in {"a", "an"} for c in attribute.children):
            return

        # A main-clause "X is a Y" must also say something about Y to count.
        relative = subject.lower_ in _RELATIVE_PRONOUNS and token.dep_ == "relcl"
        modified = any(c.dep_ in {"relcl", "acl", "prep"} for c in attribute.children)
        if not relative and not modified:
            return
        subject = _resolve_relative(subject, token)
        self._record(DefinitionKind.COPULAR, self._phrase(subject), _subtree(attribute).text)

    def _appositive(self, token: Token) -> None:
        """Record "X, a Y ...," and "a Y, X,", the determiner marking the explanation.

        Args:
            token: Candidate appositive head.
        """
        if token.dep_ != "appos" or token.head.i == token.i:
            return
        anchor = _trim(self._phrase(token.head))
        appositive = _trim(_subtree(token))
        if not len(anchor) or not len(appositive):
            return

        # A determiner marks the describing side ("IL-6, a cytokine, ...");
        # without exactly one, the direction (and often the parse) is unreliable.
        anchor_det = anchor[0].pos_ == "DET"
        appositive_det = appositive[0].pos_ == "DET"
        if appositive_det and not anchor_det:
            self._record_directed(DefinitionKind.APPOSITIVE, anchor, appositive)
        elif anchor_det and not appositive_det:
            self._record_directed(DefinitionKind.APPOSITIVE, appositive, anchor)

    def _or_gloss(self, token: Token) -> None:
        """Record "X, or Y," (but not the last item of a list "A, B, or C").

        Args:
            token: Candidate "or".
        """
        doc = self.doc
        if token.lower_ != "or" or token.i < 2 or doc[token.i - 1].text != ",":
            return
        left = self.chunks.get(token.i - 2)
        if left is None or left.end != token.i - 1:
            return

        # A separator before X means X is a list item, not a term being glossed.
        if left.start > 0 and doc[left.start - 1].text in _LIST_SEPARATORS:
            return

        # Y runs from "or" to the next comma, bracket or full stop, and is short.
        end = token.i + 1
        while end < token.sent.end and doc[end].text not in _GLOSS_END:
            end += 1
        if end == token.i + 1 or end - token.i - 1 > _MAX_OR_GLOSS_TOKENS:
            return
        self._record_pair(DefinitionKind.GLOSS, left, doc[token.i + 1 : end])

    def _parenthetical_gloss(self, opening: Token, covered: list[tuple[int, int]]) -> None:
        """Record "X (Y)" glosses that are not abbreviations, citations or statistics.

        Args:
            opening: An opening-parenthesis token.
            covered: Character ranges already explained by abbreviation pairs.
        """
        doc = self.doc
        closing = _closing_parenthesis(opening)
        if closing is None or opening.i == 0:
            return
        if overlaps_any(opening.idx, closing.idx + 1, covered):
            return

        # Drop lead-ins such as "i.e.," and "or" before judging the gloss.
        first = opening.i + 1
        while first < closing.i and doc[first].lower_ in _GLOSS_LEAD_INS:
            first += 1
        inner = doc[first : closing.i]
        self._record_pair(DefinitionKind.GLOSS, self._phrase(doc[opening.i - 1]), inner)

    # --- Helpers ------------------------------------------------------------

    def _phrase(self, token: Token) -> Span:
        """Return the noun chunk holding a token, or the token alone.

        Args:
            token: A token.

        Returns:
            The span to treat as the term.
        """
        chunk = self.chunks.get(token.i)
        return chunk if chunk is not None else self.doc[token.i : token.i + 1]

    def _weight(self, span: Span) -> float:
        """Return the largest unfamiliarity of the term words in a span.

        Args:
            span: Any span.

        Returns:
            0 to 1; 0 when the span has no term words.
        """
        return max(
            (unfamiliarity(word_zipf(t, self.familiarity)) for t in span if is_term_word(t)),
            default=0.0,
        )

    def _record_pair(self, kind: DefinitionKind, left: Span, right: Span) -> None:
        """Record whichever side of a pair is less familiar as the defined term.

        Args:
            kind: Definition kind.
            left: First side.
            right: Second side.
        """
        left_weight, right_weight = self._weight(left), self._weight(right)
        if left_weight == right_weight:
            return
        defined, gloss = (left, right) if left_weight > right_weight else (right, left)
        self._record_directed(kind, defined, gloss)

    def _record_directed(self, kind: DefinitionKind, defined: Span, gloss: Span) -> None:
        """Record a definition whose term and explanation are known, if the explanation is real.

        Args:
            kind: Definition kind.
            defined: The phrase being defined.
            gloss: The explaining phrase.
        """
        if not self._looks_like_gloss(gloss):
            return
        self._record(kind, defined, gloss.text)

    def _looks_like_gloss(self, gloss: Span) -> bool:
        """Decide whether a span reads like an explanation.

        Args:
            gloss: Candidate explanation.

        Returns:
            False for empty or long spans, figure and table references,
            citations, statistics, and spans without a word of three letters.
        """
        if not len(gloss) or len(gloss) > _MAX_GLOSS_TOKENS:
            return False
        if gloss[0].lower_ in _NOT_GLOSS_STARTS:
            return False
        if any(ch in _NOT_GLOSS_CHARS for ch in gloss.text):
            return False
        if overlaps_any(gloss.start_char, gloss.end_char, self.skip):
            return False
        return any(t.is_alpha and len(t.text) >= _MIN_GLOSS_WORD_LETTERS for t in gloss)

    def _record(self, kind: DefinitionKind, span: Span, gloss: str) -> None:
        """Record a definition of a span's technical core, if it has one.

        Args:
            kind: Definition kind.
            span: The phrase being defined.
            gloss: The explanation text.
        """
        core = term_core(span, self.familiarity)
        occurrence = occurrence_for(core, self.familiarity) if core is not None else None
        if occurrence is None or overlaps_any(occurrence.start, occurrence.end, self.skip):
            return
        self.found.append(
            Definition(
                kind=kind,
                term_key=occurrence.key,
                term_text=occurrence.text,
                gloss=gloss.strip(),
                start=occurrence.start,
                end=occurrence.end,
            )
        )


def find_definitions(doc: Doc, familiarity: Familiarity) -> list[Definition]:
    """Find the terms a parsed paragraph defines.

    Args:
        doc: The paragraph, processed by a pipeline with a parser.
        familiarity: Word-frequency source (decides which side of a gloss is the term).

    Returns:
        Definitions sorted by position.
    """
    return _Finder(doc, familiarity).run()


def _text_at(doc: Doc, index: int) -> str | None:
    """Return the lower-cased text of the token at an index, if any.

    Args:
        doc: The document.
        index: Token index.

    Returns:
        Lower-cased token text, or None past the end.
    """
    return doc[index].lower_ if 0 <= index < len(doc) else None


def _after_so_hyphen(token: Token) -> bool:
    """Check for "so-called", which flags a term without explaining it.

    Args:
        token: The "called" token.

    Returns:
        True if the two preceding tokens are "so" and "-".
    """
    doc = token.doc
    return token.i >= 2 and doc[token.i - 1].text == "-" and doc[token.i - 2].lower_ == "so"


def _child_with_dep(children: list[Token], dep: str) -> Token | None:
    """Return the first child with a dependency label.

    Args:
        children: A token's children.
        dep: Dependency label.

    Returns:
        The child, or None.
    """
    return next((c for c in children if c.dep_ == dep), None)


def _child_with_text(children: list[Token], text: str) -> Token | None:
    """Return the first child with a given lower-cased text.

    Args:
        children: A token's children.
        text: Lower-cased text to match.

    Returns:
        The child, or None.
    """
    return next((c for c in children if c.lower_ == text), None)


def _resolve_relative(subject: Token, verb: Token) -> Token:
    """Replace a relative pronoun subject ("which") by the noun it refers to.

    Args:
        subject: The verb's subject.
        verb: The verb.

    Returns:
        The noun the relative clause attaches to, or the subject unchanged.
    """
    if subject.lower_ in _RELATIVE_PRONOUNS and verb.dep_ == "relcl":
        return verb.head
    return subject


def _subtree(token: Token) -> Span:
    """Return the contiguous span covering a token's subtree.

    Args:
        token: A token.

    Returns:
        The span from its left edge to its right edge.
    """
    return token.doc[token.left_edge.i : token.right_edge.i + 1]


def _closing_parenthesis(opening: Token) -> Token | None:
    """Find the token closing a parenthesis, within the same sentence.

    Args:
        opening: An opening-parenthesis token.

    Returns:
        The matching ")" token, or None.
    """
    depth = 0
    for token in opening.doc[opening.i : opening.sent.end]:
        if token.text == "(":
            depth += 1
        elif token.text == ")":
            depth -= 1
            if depth == 0:
                return token
    return None


def _trim(span: Span) -> Span:
    """Strip punctuation from both ends of a span.

    Args:
        span: Any span.

    Returns:
        The span without leading or trailing punctuation (possibly empty).
    """
    start, end = 0, len(span)
    while start < end and span[start].is_punct:
        start += 1
    while end > start and span[end - 1].is_punct:
        end -= 1
    return span[start:end]
