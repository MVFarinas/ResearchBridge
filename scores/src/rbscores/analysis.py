"""One pass of NLP over a document, shared by both scores.

Each paragraph is parsed once by spaCy, and everything both scores need is
taken from that parse: per-sentence readability counts, candidate terms,
definitions and citation markers. Scores for paragraphs, sections and the
paper are then pooled from these analyses without re-parsing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from spacy.language import Language
from spacy.tokens import Doc

from rbscores.burden.definitions import Definition, find_definitions
from rbscores.burden.references import find_citations
from rbscores.burden.score import DefinedTerms
from rbscores.burden.terms import TermOccurrence, extract_terms
from rbscores.familiarity import Familiarity, WordfreqFamiliarity
from rbscores.nlp import load_pipeline, pipeline_label
from rbscores.readability.features import SentenceStats, is_word, sentence_stats
from rbscores.text import TextDocument, TextParagraph, check_paragraph_lengths


@dataclass(frozen=True, slots=True)
class ParagraphAnalysis:
    """Everything the scores need from one parsed paragraph.

    Attributes:
        paragraph: The paragraph.
        sentences: Per-sentence readability counts.
        sentence_words: The words of each sentence (for the Flesch-Kincaid
            baseline), aligned with ``sentences``.
        terms: Candidate term occurrences.
        definitions: Terms the paragraph defines.
        citations: Citation marker spans.
    """

    paragraph: TextParagraph
    sentences: tuple[SentenceStats, ...]
    sentence_words: tuple[tuple[str, ...], ...]
    terms: tuple[TermOccurrence, ...]
    definitions: tuple[Definition, ...]
    citations: tuple[tuple[int, int], ...]

    @property
    def words(self) -> int:
        """Words in the paragraph."""
        return sum(s.words for s in self.sentences)


@dataclass(frozen=True, slots=True)
class DocumentAnalysis:
    """The analyses of every paragraph of a document.

    Attributes:
        document: The document.
        paragraphs: One analysis per paragraph, in document order.
        defined: Every term the document defines.
        model: Name of the spaCy pipeline used.
    """

    document: TextDocument
    paragraphs: tuple[ParagraphAnalysis, ...]
    defined: DefinedTerms
    model: str

    def for_section(self, section_id: str) -> tuple[ParagraphAnalysis, ...]:
        """Return the analyses of one section's paragraphs.

        Args:
            section_id: Section ID.

        Returns:
            Paragraph analyses in document order.
        """
        return tuple(p for p in self.paragraphs if p.paragraph.section_id == section_id)


def analyse_document(
    document: TextDocument,
    *,
    nlp: Language | None = None,
    familiarity: Familiarity | None = None,
) -> DocumentAnalysis:
    """Parse every paragraph once and extract what both scores need.

    Args:
        document: The document.
        nlp: spaCy pipeline with a parser; defaults to :func:`rbscores.nlp.load_pipeline`.
        familiarity: Word-frequency source; defaults to :class:`WordfreqFamiliarity`.

    Returns:
        The document analysis.

    Raises:
        rbscores.text.ParagraphTooLongError: If a paragraph is longer than
            :data:`rbscores.text.MAX_PARAGRAPH_CHARS`.
    """
    # Refuse over-long paragraphs before loading or running the parser.
    check_paragraph_lengths(document)
    pipeline = nlp or load_pipeline()
    lookup = familiarity or WordfreqFamiliarity()
    paragraphs = document.iter_paragraphs()
    docs = pipeline.pipe(p.text for p in paragraphs)
    analyses = tuple(
        analyse_paragraph(paragraph, doc, lookup)
        for paragraph, doc in zip(paragraphs, docs, strict=True)
    )
    defined = DefinedTerms.from_definitions(
        (a.paragraph.id, d) for a in analyses for d in a.definitions
    )
    return DocumentAnalysis(
        document=document, paragraphs=analyses, defined=defined, model=pipeline_label(pipeline)
    )


def analyse_paragraph(
    paragraph: TextParagraph, doc: Doc, familiarity: Familiarity
) -> ParagraphAnalysis:
    """Extract readability counts, terms, definitions and citations from one parse.

    Args:
        paragraph: The paragraph.
        doc: Its spaCy parse.
        familiarity: Word-frequency source.

    Returns:
        The paragraph analysis.
    """
    stats = sentence_stats(doc, familiarity)
    words = tuple(
        tuple(t.text for t in sentence if is_word(t))
        for sentence in doc.sents
        if any(is_word(t) for t in sentence)
    )
    return ParagraphAnalysis(
        paragraph=paragraph,
        sentences=tuple(stats),
        sentence_words=words,
        terms=tuple(extract_terms(doc, familiarity)),
        definitions=tuple(find_definitions(doc, familiarity)),
        citations=tuple(find_citations(paragraph.text)),
    )


def pooled_sentences(analyses: Sequence[ParagraphAnalysis]) -> list[SentenceStats]:
    """Pool the sentences of several paragraphs.

    Args:
        analyses: Paragraph analyses.

    Returns:
        All their sentence counts, in order.
    """
    return [s for a in analyses for s in a.sentences]
