"""ResearchBridge Track R: readability and prior-knowledge burden scores.

**Both scores are PROVISIONAL.** They implement the draft definitions in
decisions.md §2.4 and have not been validated against human judgements. They
must not be shown to readers until validation 2 (lay readers' pairwise
"which is harder?" judgements) and the burden validation (lay readers' "terms
I don't know" marks) are done. Every score report carries
:data:`PROVISIONAL_NOTICE`.

The two scores stay separable (decisions.md §2.4):

* **Readability** (:mod:`rbscores.readability`) measures how the text is
  written: sentence length, syntactic depth, nominalisations, passive voice
  and jargon density, combined into a provisional composite.
* **Prior-knowledge burden** (:mod:`rbscores.burden`) measures what the text
  assumes: technical terms the text does not define, weighted by how
  unfamiliar they are, plus the external results it leans on, per 1,000 words.

Quick use::

    from rbscores import load_document, score_document

    report = score_document(load_document("paper.xml"))
    report.paper.composite  # provisional readability composite (higher = harder)
    report.paper.burden.burden_per_1000
    report.paper.burden.undefined_terms[:10]  # what to annotate first
"""

from rbscores.scoring import (
    ScoreReport,
    UnitScore,
    rank_undefined_terms,
    score_document,
    score_text,
)
from rbscores.status import METHOD_VERSION, PROVISIONAL, PROVISIONAL_NOTICE
from rbscores.text import TextDocument, document_from_article, document_from_text, load_document

__all__ = [
    "METHOD_VERSION",
    "PROVISIONAL",
    "PROVISIONAL_NOTICE",
    "ScoreReport",
    "TextDocument",
    "UnitScore",
    "document_from_article",
    "document_from_text",
    "load_document",
    "rank_undefined_terms",
    "score_document",
    "score_text",
]
