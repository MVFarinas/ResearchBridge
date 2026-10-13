"""Tests for whole-document scoring, reports and the ranked-term API."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from spacy.language import Language

from rbscores import PROVISIONAL_NOTICE, rank_undefined_terms, score_document, score_text
from rbscores.familiarity import Familiarity, WordfreqFamiliarity
from rbscores.readability.composite import ReferenceStats
from rbscores.text import document_from_text, load_document

SyntheticFactory = Callable[..., Familiarity]

SYNTHETIC_TEXT = (
    "Body mass index (BMI) was recorded. Patients with high BMI had more nephrons.\n\n"
    "Apoptosis was measured. Nephrons and apoptosis were linked."
)


@pytest.fixture
def familiarity(make_familiarity: SyntheticFactory) -> Familiarity:
    """Synthetic familiarity where a few technical words are rare."""
    return make_familiarity({"bmi": 0.0, "nephrons": 1.0, "nephron": 1.0, "apoptosis": 2.75})


def test_document_scores_at_every_level(
    nlp: Language, familiarity: Familiarity, synthetic_reference: ReferenceStats
) -> None:
    """Paragraph, section and paper scores exist and burden pools the right terms."""
    report = score_document(
        document_from_text(SYNTHETIC_TEXT),
        nlp=nlp,
        familiarity=familiarity,
        reference=synthetic_reference,
    )
    assert [p.id for p in report.paragraphs] == ["p1", "p2"]
    assert [s.id for s in report.sections] == ["text"]
    paper = report.paper
    assert paper.readability is not None
    assert paper.readability.sentences == 4
    assert paper.composite == pytest.approx(sum(paper.readability.values().values()) / 5)

    # BMI is defined in p1, so only nephron and apoptosis are undefined.
    keys = [t.key for t in paper.burden.undefined_terms]
    assert keys == ["nephron", "apoptosis"]
    assert "bmi" in paper.burden.defined_terms
    expected = (1.0 + 0.5) * 1000 / paper.burden.words
    assert paper.burden.burden_per_1000 == pytest.approx(expected)

    # The p2 paragraph has both terms; p1 only nephron.
    assert [t.key for t in report.paragraphs[0].burden.undefined_terms] == ["nephron"]
    nephron = paper.burden.undefined_terms[0]
    assert {loc.paragraph_id for loc in nephron.locations} == {"p1", "p2"}


def test_report_dict_is_json_and_provisional(
    nlp: Language, familiarity: Familiarity, synthetic_reference: ReferenceStats
) -> None:
    """The JSON report carries the provisional notice, versions and definitions."""
    report = score_document(
        document_from_text(SYNTHETIC_TEXT),
        nlp=nlp,
        familiarity=familiarity,
        reference=synthetic_reference,
    )
    data = json.loads(json.dumps(report.to_dict(top_terms=1, paragraphs=False)))
    assert data["provisional"] is True
    assert data["notice"] == PROVISIONAL_NOTICE
    assert data["reference_version"] == "synthetic-test-reference"
    assert data["spacy_model"] == "en_core_web_sm-3.8.0"
    assert data["paragraphs"] is None
    paper_burden = data["paper"]["burden"]
    assert paper_burden["undefined_term_count"] == 2
    assert len(paper_burden["undefined_terms"]) == 1
    assert data["definitions"][0]["kind"] == "abbreviation"
    assert data["definitions"][0]["term"] == "BMI"


def test_score_text_returns_the_paper_unit(
    nlp: Language, familiarity: Familiarity, synthetic_reference: ReferenceStats
) -> None:
    """score_text pools all paragraphs into one unit."""
    unit = score_text(
        SYNTHETIC_TEXT, nlp=nlp, familiarity=familiarity, reference=synthetic_reference
    )
    assert unit.level == "paper"
    assert unit.readability is not None
    assert unit.readability.sentences == 4


def test_rank_undefined_terms_covers_abstracts(nlp: Language, jats_fixtures: Path) -> None:
    """Annotation targeting ranks terms across the whole document, abstracts included."""
    document = load_document(jats_fixtures / "elife-93719-pmc-s3.xml")
    ranked = rank_undefined_terms(document, nlp=nlp, familiarity=WordfreqFamiliarity(), limit=200)
    assert ranked
    weights = [t.weight for t in ranked]
    assert weights == sorted(weights, reverse=True)
    assert all(0 < w <= 1 for w in weights)
    located_in = {loc.paragraph_id for t in ranked for loc in t.locations}
    assert any(pid.startswith("abs") for pid in located_in)


def test_real_lay_text_scores_easier_than_its_technical_version(nlp: Language) -> None:
    """A plain sentence pair (written for this test) ranks as expected on both scores."""
    technical = (
        "Pharmacological inhibition of mTORC1 attenuated the phosphorylation of S6K1, "
        "which was subsequently quantified by immunoblotting of hepatocyte lysates."
    )
    plain = "The drug blocked a growth signal in liver cells. We measured this with a lab test."
    hard = score_text(technical, nlp=nlp)
    easy = score_text(plain, nlp=nlp)
    assert hard.composite is not None
    assert easy.composite is not None
    assert easy.composite < hard.composite
    assert easy.burden.burden_per_1000 < hard.burden.burden_per_1000
