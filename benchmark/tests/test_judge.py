"""Tests of the LLM judge harness with the fake client (SYNTHETIC data only)."""

from __future__ import annotations

import json

import pytest

from rbbench.claims import Method, decompose
from rbbench.clients import ClientKind, make_client
from rbbench.fakes import SYNTHETIC_RATIONALE
from rbbench.judge.harness import (
    JudgeError,
    JudgeItem,
    build_items,
    judge_items,
    parse_judgement,
    render_codes,
    render_item,
    response_schema,
)
from rbbench.rewrite.harness import RewriteRecord
from rbbench.rewrite.markup import parse_rewrite
from rbbench.rubric import Rubric, Unit
from rbcore.config import Settings
from rbcore.llm import FakeLLMClient


def _synthetic_rewrite(model: str = "fake-deterministic") -> RewriteRecord:
    """A SYNTHETIC one-paragraph rewrite."""
    output = (
        '<rewrite id="p1">Synthetic drug reduced symptoms. '
        "<added>Symptoms are signs of illness.</added></rewrite>"
    )
    return RewriteRecord(
        rewrite_id="synthetic|default|1",
        passage_id="synthetic",
        paper_key="synthetic",
        arm="default",
        requested_model=model,
        model=model,
        prompt_version="rewrite_v1",
        prompt_sha256="0" * 64,
        temperature=None,
        timestamp="2026-10-13T00:00:00Z",
        synthetic=True,
        valid=True,
        errors=(),
        warnings=(),
        paragraphs=parse_rewrite(output, ["p1"]).paragraphs,
        source=(("p1", "Synthetic drug may reduce symptoms in 20 adults."),),
        raw_output=output,
        stop_reason="end_turn",
        input_tokens=0,
        output_tokens=0,
    )


def test_build_items_covers_claims_then_paragraphs() -> None:
    """Every claim and every paragraph becomes one judge item."""
    rewrite = _synthetic_rewrite()
    claims = decompose(rewrite, Method.SENTENCES)
    items = build_items([rewrite], claims)
    assert [(i.unit, i.unit_id) for i in items] == [
        (Unit.CLAIM, "synthetic|default|1#p1#c1"),
        (Unit.CLAIM, "synthetic|default|1#p1#c2"),
        (Unit.PARAGRAPH, "synthetic|default|1#p1"),
    ]
    assert items[1].in_addition
    assert "<added>Symptoms are signs of illness.</added>" in items[0].rewritten_markup


def test_prompt_lists_every_code_of_the_unit(rubric: Rubric) -> None:
    """The rendered questions and schema name exactly the unit's codes."""
    codes = rubric.codes_for(Unit.CLAIM)
    rendered = render_codes(codes)
    for code in codes:
        assert f"- {code.id}:" in rendered
    schema = json.loads(response_schema(codes))
    assert schema["labels"]["support"] == ["supported", "unsupported", "contradicted"]
    assert "dropped_limitation" not in schema["labels"]


def test_fake_judge_produces_valid_synthetic_ratings(rubric: Rubric) -> None:
    """With the fake client every item is labelled validly and marked synthetic."""
    rewrite = _synthetic_rewrite()
    items = build_items([rewrite], decompose(rewrite, Method.SENTENCES))
    client, model = make_client(ClientKind.FAKE, role="judge", settings=Settings())
    records = judge_items(items, rubric, client, judge_model=model)
    assert all(r.valid for r in records), [r.errors for r in records]
    assert all(r.synthetic and r.rationale == SYNTHETIC_RATIONALE for r in records)
    assert records[0].judge_id == "judge:fake-deterministic:judge_v1"
    assert set(records[-1].labels) == {"dropped_limitation"}
    rating = records[0].to_rating()
    assert rating.rater_id == records[0].judge_id
    assert rubric.validate_labels(Unit.CLAIM, rating.labels) == []
    # The prompt carried the claim and the aligned source paragraph.
    prompt = client.calls[0].messages[0].content  # type: ignore[attr-defined]
    assert 'from_marked_addition="false"' in prompt
    assert "Synthetic drug may reduce symptoms in 20 adults." in prompt


def test_invalid_judge_output_is_recorded_not_guessed(rubric: Rubric) -> None:
    """Bad JSON or labels outside the rubric give an invalid record with the error."""
    rewrite = _synthetic_rewrite()
    items = build_items([rewrite], decompose(rewrite, Method.SENTENCES))[:1]
    client = FakeLLMClient(lambda _request: '{"labels": {"support": "probably"}}')
    (record,) = judge_items(items, rubric, client, judge_model="fake-deterministic")
    assert not record.valid
    assert record.labels == {}
    assert "probably" in record.errors[0]
    with pytest.raises(JudgeError):
        record.to_rating()


def test_judge_may_not_grade_its_own_rewrite(rubric: Rubric) -> None:
    """decisions.md §1.4: the judge model must differ from the generator."""
    rewrite = _synthetic_rewrite(model="model-x")
    items = build_items([rewrite], decompose(rewrite, Method.SENTENCES))
    with pytest.raises(JudgeError, match="wrote this rewrite"):
        judge_items(items, rubric, FakeLLMClient(), judge_model="model-x")


def test_parse_judgement_accepts_fenced_json(rubric: Rubric) -> None:
    """A fenced JSON answer with every paragraph code parses."""
    output = '```json\n{"labels": {"dropped_limitation": "yes"}, "rationale": "r"}\n```'
    assert parse_judgement(output, rubric, Unit.PARAGRAPH) == ({"dropped_limitation": "yes"}, "r")
    with pytest.raises(JudgeError, match="missing code"):
        parse_judgement('{"labels": {}}', rubric, Unit.PARAGRAPH)
    with pytest.raises(JudgeError, match="no JSON"):
        parse_judgement("no", rubric, Unit.PARAGRAPH)


def test_paragraph_item_renders_without_a_claim() -> None:
    """Paragraph items show the paragraph but no claim block."""
    item = JudgeItem(Unit.PARAGRAPH, "r#p1", (("p1", "S."),), "p1", "R.")
    text = render_item(item)
    assert "<claim" not in text
    assert '<aligned_source_paragraph id="p1">' in text
