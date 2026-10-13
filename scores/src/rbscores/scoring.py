"""Score reports per paragraph, section and paper, and the ranked-term API.

Every report is PROVISIONAL and says so (:data:`rbscores.status.PROVISIONAL_NOTICE`).
Readability and burden are reported side by side and never combined.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from spacy.language import Language

from rbscores.analysis import DocumentAnalysis, ParagraphAnalysis, analyse_document
from rbscores.burden.score import (
    BurdenParams,
    BurdenResult,
    DefinedTerms,
    LocatedTerm,
    TermBurden,
    compute_burden,
)
from rbscores.familiarity import Familiarity
from rbscores.readability.composite import ReferenceStats, composite_score, load_reference, z_scores
from rbscores.readability.features import ReadabilityFeatures, aggregate
from rbscores.status import METHOD_VERSION, PROVISIONAL, PROVISIONAL_NOTICE
from rbscores.text import TextDocument, document_from_text


@dataclass(frozen=True, slots=True)
class UnitScore:
    """Both scores for one unit of text.

    Attributes:
        level: "paragraph", "section" or "paper".
        id: Paragraph or section ID, or "paper".
        title: Section title, if any.
        readability: The five features, or None for a unit without words.
        z_scores: Each feature's z-score against the reference, or None.
        composite: PROVISIONAL composite readability (higher = harder), or None.
        burden: PROVISIONAL prior-knowledge burden.
    """

    level: str
    id: str
    title: str | None
    readability: ReadabilityFeatures | None
    z_scores: dict[str, float] | None
    composite: float | None
    burden: BurdenResult

    def to_dict(self, *, top_terms: int | None = 25) -> dict[str, Any]:
        """Return the unit's scores for JSON output.

        Args:
            top_terms: How many ranked undefined terms to include (None for all).

        Returns:
            A JSON-serialisable mapping.
        """
        terms = self.burden.undefined_terms
        shown = terms if top_terms is None else terms[:top_terms]
        return {
            "level": self.level,
            "id": self.id,
            "title": self.title,
            "readability": {
                "features": self.readability.as_dict() if self.readability else None,
                "z_scores": self.z_scores,
                "composite": self.composite,
            },
            "burden": {
                "words": self.burden.words,
                "burden_per_1000": self.burden.burden_per_1000,
                "term_burden_per_1000": self.burden.term_burden_per_1000,
                "citation_burden_per_1000": self.burden.citation_burden_per_1000,
                "citations": self.burden.citations,
                "undefined_term_count": len(terms),
                "undefined_terms": [term_to_dict(t) for t in shown],
                "defined_terms": list(self.burden.defined_terms),
            },
        }


@dataclass(frozen=True, slots=True)
class ScoreReport:
    """Scores for a whole document.

    Attributes:
        title: Document title.
        identifier: DOI or file name.
        source: "jats" or "text".
        model: spaCy pipeline used.
        reference_version: Version of the composite's reference statistics.
        paper: The paper unit (body text; see :mod:`rbscores.text`).
        sections: One score per section.
        paragraphs: One score per paragraph.
        analysis: The underlying analysis (definitions, term occurrences).
    """

    title: str | None
    identifier: str | None
    source: str
    model: str
    reference_version: str
    paper: UnitScore
    sections: tuple[UnitScore, ...]
    paragraphs: tuple[UnitScore, ...]
    analysis: DocumentAnalysis

    def to_dict(self, *, top_terms: int | None = 25, paragraphs: bool = True) -> dict[str, Any]:
        """Return the report for JSON output, with the provisional notice.

        Args:
            top_terms: Ranked undefined terms to include per unit (None for all).
            paragraphs: Include per-paragraph scores.

        Returns:
            A JSON-serialisable mapping.
        """
        return {
            "provisional": PROVISIONAL,
            "notice": PROVISIONAL_NOTICE,
            "method_version": METHOD_VERSION,
            "reference_version": self.reference_version,
            "spacy_model": self.model,
            "document": {"title": self.title, "identifier": self.identifier, "source": self.source},
            "paper": self.paper.to_dict(top_terms=top_terms),
            "sections": [s.to_dict(top_terms=top_terms) for s in self.sections],
            "paragraphs": (
                [p.to_dict(top_terms=top_terms) for p in self.paragraphs] if paragraphs else None
            ),
            "definitions": [
                {
                    "paragraph_id": paragraph_id,
                    "kind": str(d.kind),
                    "term": d.term_text,
                    "term_key": d.term_key,
                    "gloss": d.gloss,
                    "start": d.start,
                    "end": d.end,
                }
                for paragraph_id, d in self.analysis.defined.definitions
            ],
        }


def term_to_dict(term: TermBurden) -> dict[str, Any]:
    """Return one ranked term for JSON output.

    Args:
        term: A ranked undefined term.

    Returns:
        A JSON-serialisable mapping.
    """
    return {
        "term": term.text,
        "key": term.key,
        "weight": round(term.weight, 4),
        "min_zipf": round(term.min_zipf, 2),
        "count": term.count,
        "abbreviation": term.abbreviation,
        "locations": [
            {"paragraph_id": loc.paragraph_id, "start": loc.start, "end": loc.end}
            for loc in term.locations
        ],
    }


def score_unit(
    analyses: Sequence[ParagraphAnalysis],
    *,
    level: str,
    unit_id: str,
    title: str | None,
    defined: DefinedTerms,
    reference: ReferenceStats,
    params: BurdenParams | None = None,
) -> UnitScore:
    """Score a set of paragraphs as one unit.

    Args:
        analyses: The unit's paragraph analyses.
        level: "paragraph", "section" or "paper".
        unit_id: The unit's ID.
        title: The unit's title, if any.
        defined: Terms the whole document defines.
        reference: Reference statistics for the composite.
        params: Burden settings.

    Returns:
        The unit's scores.
    """
    # Readability pools the unit's sentences.
    features = aggregate([s for a in analyses for s in a.sentences])
    zs = z_scores(features, reference) if features else None
    composite = composite_score(features, reference) if features else None

    # Burden counts each term once per unit, located by paragraph.
    located = [LocatedTerm(a.paragraph.id, t) for a in analyses for t in a.terms]
    burden = compute_burden(
        located,
        words=sum(a.words for a in analyses),
        citations=sum(len(a.citations) for a in analyses),
        defined=defined,
        params=params,
    )
    return UnitScore(
        level=level,
        id=unit_id,
        title=title,
        readability=features,
        z_scores=zs,
        composite=composite,
        burden=burden,
    )


def score_analysis(
    analysis: DocumentAnalysis,
    *,
    reference: ReferenceStats | None = None,
    params: BurdenParams | None = None,
) -> ScoreReport:
    """Score an analysed document at every level.

    Args:
        analysis: The document analysis.
        reference: Reference statistics; defaults to the packaged ones.
        params: Burden settings.

    Returns:
        The report.
    """
    ref = reference or load_reference()
    document = analysis.document
    defined = analysis.defined

    # Paragraph and section units.
    paragraph_scores = tuple(
        score_unit(
            (a,),
            level="paragraph",
            unit_id=a.paragraph.id,
            title=None,
            defined=defined,
            reference=ref,
            params=params,
        )
        for a in analysis.paragraphs
    )
    section_scores = tuple(
        score_unit(
            analysis.for_section(section.id),
            level="section",
            unit_id=section.id,
            title=section.title,
            defined=defined,
            reference=ref,
            params=params,
        )
        for section in document.sections
    )

    # The paper unit: the main text (abstracts only if there is nothing else).
    paper_ids = {p.id for s in document.paper_sections for p in s.paragraphs}
    paper = score_unit(
        [a for a in analysis.paragraphs if a.paragraph.id in paper_ids],
        level="paper",
        unit_id="paper",
        title=document.title,
        defined=defined,
        reference=ref,
        params=params,
    )
    return ScoreReport(
        title=document.title,
        identifier=document.identifier,
        source=document.source,
        model=analysis.model,
        reference_version=ref.version,
        paper=paper,
        sections=section_scores,
        paragraphs=paragraph_scores,
        analysis=analysis,
    )


def score_document(
    document: TextDocument,
    *,
    nlp: Language | None = None,
    familiarity: Familiarity | None = None,
    reference: ReferenceStats | None = None,
    params: BurdenParams | None = None,
) -> ScoreReport:
    """Analyse and score a document.

    Args:
        document: The document.
        nlp: spaCy pipeline; defaults to the configured one.
        familiarity: Word-frequency source; defaults to wordfreq.
        reference: Reference statistics; defaults to the packaged ones.
        params: Burden settings.

    Returns:
        The PROVISIONAL score report.

    Raises:
        rbscores.text.ParagraphTooLongError: If a paragraph is too long to analyse.
    """
    analysis = analyse_document(document, nlp=nlp, familiarity=familiarity)
    return score_analysis(analysis, reference=reference, params=params)


def score_text(
    text: str,
    *,
    nlp: Language | None = None,
    familiarity: Familiarity | None = None,
    reference: ReferenceStats | None = None,
    params: BurdenParams | None = None,
) -> UnitScore:
    """Score a plain text as one unit (its paragraphs pooled).

    Args:
        text: The text; blank lines separate paragraphs.
        nlp: spaCy pipeline; defaults to the configured one.
        familiarity: Word-frequency source; defaults to wordfreq.
        reference: Reference statistics; defaults to the packaged ones.
        params: Burden settings.

    Returns:
        The paper-level PROVISIONAL scores.

    Raises:
        rbscores.text.ParagraphTooLongError: If a paragraph is too long to analyse.
    """
    report = score_document(
        document_from_text(text),
        nlp=nlp,
        familiarity=familiarity,
        reference=reference,
        params=params,
    )
    return report.paper


def rank_undefined_terms(
    document: TextDocument,
    *,
    limit: int | None = None,
    nlp: Language | None = None,
    familiarity: Familiarity | None = None,
    params: BurdenParams | None = None,
) -> tuple[TermBurden, ...]:
    """Rank a whole document's undefined, unfamiliar terms (annotation targeting).

    Unlike the paper score, this covers every scored paragraph, abstracts
    included, since every passage a reader sees can be annotated. Each term
    lists all its locations (paragraph ID and character offsets).

    Args:
        document: The document.
        limit: Return at most this many terms (None for all).
        nlp: spaCy pipeline; defaults to the configured one.
        familiarity: Word-frequency source; defaults to wordfreq.
        params: Burden settings.

    Returns:
        Undefined terms, most burdensome first. PROVISIONAL, like the scores.

    Raises:
        rbscores.text.ParagraphTooLongError: If a paragraph is too long to analyse.
    """
    analysis = analyse_document(document, nlp=nlp, familiarity=familiarity)
    located = [LocatedTerm(a.paragraph.id, t) for a in analysis.paragraphs for t in a.terms]
    burden = compute_burden(
        located,
        words=sum(a.words for a in analysis.paragraphs),
        citations=0,
        defined=analysis.defined,
        params=params,
    )
    terms = burden.undefined_terms
    return terms if limit is None else terms[:limit]
