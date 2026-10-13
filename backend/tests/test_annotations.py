"""Annotations: W3C shapes, anchoring, provenance rules, history and gating (synthetic)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from support import synthetic_code, synthetic_content, synthetic_version

from rb_backend.annotations.models import Annotation, AnnotationRevision, Provenance, Report, Vote
from rb_backend.annotations.w3c import validate_anchor, validate_body, validate_target
from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import PaperVersion, Paragraph

TEXT = "Synthetic paragraph 1 about mitochondria (not real text)."


def target(exact: str = "mitochondria", start: int = 28, **quote: str) -> dict[str, Any]:
    """A synthetic W3C target for the synthetic paragraph text."""
    return {
        "source": "PMC900000001.1",
        "selector": [
            {"type": "TextQuoteSelector", "exact": exact, **quote},
            {"type": "TextPositionSelector", "start": start, "end": start + len(exact)},
        ],
    }


BODY = {
    "type": "TextualBody",
    "value": "Synthetic explanation (test only).",
    "format": "text/plain",
}


# --- Pure W3C validation -------------------------------------------------------------


def test_valid_target_returns_both_selectors() -> None:
    """A target with one quote and one position selector is accepted."""
    quote, position = validate_target(target(prefix="about ", suffix=" (not"))
    assert quote["exact"] == "mitochondria"
    assert (position["start"], position["end"]) == (28, 40)
    assert TEXT[28:40] == "mitochondria"


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ([], "JSON object"),
        ({"selector": []}, "source"),
        ({"source": "x", "selector": {}}, "must be a list"),
        ({"source": "x", "selector": [{"type": "TextQuoteSelector", "exact": "a"}]}, "exactly one"),
        (
            {
                "source": "x",
                "selector": [
                    {"type": "TextQuoteSelector", "exact": ""},
                    {"type": "TextPositionSelector", "start": 0, "end": 1},
                ],
            },
            "exact must be",
        ),
        (
            {
                "source": "x",
                "selector": [
                    {"type": "TextQuoteSelector", "exact": "ab"},
                    {"type": "TextPositionSelector", "start": 5, "end": 4},
                ],
            },
            "start < end",
        ),
        (
            {
                "source": "x",
                "selector": [
                    {"type": "TextQuoteSelector", "exact": "ab"},
                    {"type": "TextPositionSelector", "start": True, "end": 2},
                ],
            },
            "integers",
        ),
        (
            {
                "source": "x",
                "selector": [
                    {"type": "TextQuoteSelector", "exact": "abc"},
                    {"type": "TextPositionSelector", "start": 0, "end": 2},
                ],
            },
            "span length",
        ),
    ],
)
def test_invalid_targets_are_refused(bad: object, message: str) -> None:
    """Malformed targets raise with a specific message."""
    with pytest.raises(ValidationError, match=message):
        validate_target(bad)


def test_anchor_must_match_text_prefix_and_suffix() -> None:
    """Selectors must point at the quoted text, with matching context."""
    validate_anchor(target(prefix="about ", suffix=" (not"), TEXT)
    with pytest.raises(ValidationError, match="not at the stated position"):
        validate_anchor(target(start=27), TEXT)
    with pytest.raises(ValidationError, match="prefix"):
        validate_anchor(target(prefix="beyond "), TEXT)
    with pytest.raises(ValidationError, match="suffix"):
        validate_anchor(target(suffix=" yes"), TEXT)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"type": "Text", "value": "x"}, "TextualBody"),
        ({"type": "TextualBody", "value": "  "}, "non-empty"),
        ({"type": "TextualBody", "value": "<b>x</b>", "format": "text/html"}, "format"),
        ({"type": "TextualBody", "value": "x", "purpose": "hacking"}, "purpose"),
    ],
)
def test_invalid_bodies_are_refused(body: dict[str, object], message: str) -> None:
    """Bodies are plain text or Markdown TextualBody values; HTML is refused."""
    with pytest.raises(ValidationError, match=message):
        validate_body(body)
    validate_body(BODY)


# --- Database behaviour ---------------------------------------------------------------


@pytest.fixture
def paragraph(db: None) -> Paragraph:
    """The first synthetic paragraph of an approved synthetic CC BY paper."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "CC BY")
    evaluate_version(version)
    return Paragraph.objects.get(version=version, stable_id="body-p1")


def make(paragraph: Paragraph, **fields: Any) -> Annotation:
    """Create a synthetic annotation on a paragraph."""
    values: dict[str, Any] = {
        "paper_version": paragraph.version,
        "paragraph": paragraph,
        "target": target(),
        "body": BODY,
        "provenance": Provenance.LLM,
        "model": "synthetic-model-id",
        "prompt_version": "synthetic-prompt-v0",
    }
    values.update(fields)
    return Annotation.objects.create(**values)


def test_annotation_records_anchor_and_first_revision(paragraph: Paragraph) -> None:
    """Creation stores the paragraph ID and text hash and revision 1."""
    annotation = make(paragraph)
    assert annotation.paragraph_stable_id == "body-p1"
    assert annotation.paragraph_text_sha256 == paragraph.text_sha256
    assert annotation.needs_disclaimer
    (revision,) = annotation.revisions.all()
    assert (revision.number, revision.provenance, revision.model) == (
        1,
        Provenance.LLM,
        "synthetic-model-id",
    )


def test_edit_appends_revision_and_verification_does_not(paragraph: Paragraph) -> None:
    """Content edits are versioned; verification alone is not a content change."""
    user = get_user_model().objects.create_user("synthetic-editor")
    annotation = make(paragraph)
    annotation.body = {**BODY, "value": "Synthetic corrected explanation."}
    annotation.provenance = Provenance.LLM_EDITED
    annotation.save(editor=user)
    annotation.verified_at = datetime(2026, 10, 13, tzinfo=UTC)
    annotation.verified_by = user
    annotation.save()

    revisions = list(AnnotationRevision.objects.filter(annotation=annotation))
    assert [(r.number, r.provenance) for r in revisions] == [
        (1, Provenance.LLM),
        (2, Provenance.LLM_EDITED),
    ]
    assert revisions[1].editor == user
    assert revisions[0].body == BODY
    assert not annotation.needs_disclaimer


def test_mismatched_anchor_is_refused_on_creation(paragraph: Paragraph) -> None:
    """An annotation whose quote is not where it claims cannot be created."""
    with pytest.raises(ValidationError, match="not at the stated position"):
        make(paragraph, target=target(start=3))
    assert not Annotation.objects.exists()


def test_paragraph_from_another_version_is_refused(paragraph: Paragraph) -> None:
    """The paragraph must belong to the annotated version."""
    other = synthetic_version(pmcid="PMC900000002")
    with pytest.raises(ValidationError, match="different paper version"):
        make(paragraph, paper_version=other)


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"provenance": Provenance.LLM, "model": ""}, "annotation_llm_has_model_and_prompt"),
        (
            {"provenance": Provenance.LLM_EDITED, "prompt_version": ""},
            "annotation_llm_has_model_and_prompt",
        ),
        ({"provenance": Provenance.HUMAN}, "annotation_human_has_no_model"),
    ],
)
def test_provenance_rules_are_database_constraints(
    paragraph: Paragraph, fields: dict[str, Any], constraint: str
) -> None:
    """LLM provenance names model and prompt; human provenance names neither."""
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        make(paragraph, **fields)


def test_votes_and_reports_have_their_rules(paragraph: Paragraph) -> None:
    """One vote per reader, only +1/-1; resolved reports need a time."""
    annotation = make(paragraph)
    user = get_user_model().objects.create_user("synthetic-reader")
    Vote.objects.create(annotation=annotation, voter=user, value=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        Vote.objects.create(annotation=annotation, voter=user, value=-1)
    other = get_user_model().objects.create_user("synthetic-reader-2")
    with pytest.raises(IntegrityError), transaction.atomic():
        Vote.objects.create(annotation=annotation, voter=other, value=5)
    with pytest.raises(IntegrityError), transaction.atomic():
        Report.objects.create(
            annotation=annotation, reason=Report.Reason.SPAM, status=Report.Status.UPHELD
        )


def test_annotations_follow_the_licence_gate(paragraph: Paragraph) -> None:
    """Annotations quote text, so they are shown only where the text may be shown."""
    annotation = make(paragraph)
    assert list(Annotation.objects.displayable()) == [annotation]
    assert not Annotation.objects.rewriteable().exists()

    # The paper's licence turns out to be TDM: its annotations disappear too.
    version: PaperVersion = paragraph.version
    version.licence_records.update(raw_value="TDM")
    evaluate_version(version)
    assert not Annotation.objects.displayable().exists()


def test_orphaned_annotation_is_withheld(paragraph: Paragraph) -> None:
    """If re-ingestion removes the paragraph, the annotation stays but is not shown."""
    annotation = make(paragraph)
    paragraph.delete()
    annotation.refresh_from_db()
    assert annotation.paragraph is None
    assert annotation.paragraph_stable_id == "body-p1"
    assert not Annotation.objects.displayable().exists()
