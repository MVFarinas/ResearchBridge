"""Tests of claim decomposition (SYNTHETIC rewrites and model outputs)."""

from __future__ import annotations

import json

import pytest

from rbbench.claims import (
    DecompositionError,
    Method,
    decompose,
    format_rewritten_paragraphs,
    parse_decomposition,
    sentence_claims,
)
from rbbench.clients import ClientKind, make_client
from rbbench.rewrite.harness import RewriteRecord
from rbbench.rewrite.markup import parse_rewrite
from rbcore.config import Settings
from rbcore.llm import FakeLLMClient

SYNTHETIC_OUTPUT = (
    '<rewrite id="p1">Synthetic mice lived longer. <added>Mice are mammals.</added> '
    "The effect may be small.</rewrite>"
    '<rewrite id="p2">Synthetic second paragraph.</rewrite>'
)


def _synthetic_rewrite(valid: bool = True) -> RewriteRecord:
    """A SYNTHETIC rewrite record with two paragraphs."""
    parsed = parse_rewrite(SYNTHETIC_OUTPUT, ["p1", "p2"])
    return RewriteRecord(
        rewrite_id="synthetic:discussion|default|1",
        passage_id="synthetic:discussion",
        paper_key="synthetic",
        arm="default",
        requested_model="fake",
        model="fake",
        prompt_version="rewrite_v1",
        prompt_sha256="0" * 64,
        temperature=None,
        timestamp="2026-10-13T00:00:00Z",
        synthetic=True,
        valid=valid,
        errors=() if valid else ("synthetic error",),
        warnings=(),
        paragraphs=parsed.paragraphs,
        source=(("p1", "Source one."), ("p2", "Source two.")),
        raw_output=SYNTHETIC_OUTPUT,
        stop_reason="end_turn",
        input_tokens=0,
        output_tokens=0,
    )


def test_sentence_fallback_flags_the_marked_addition() -> None:
    """One claim per sentence; the added sentence is flagged in_addition."""
    paragraph = _synthetic_rewrite().paragraphs[0]
    assert sentence_claims(paragraph) == [
        ("Synthetic mice lived longer.", False),
        ("Mice are mammals.", True),
        ("The effect may be small.", False),
    ]


def test_sentence_method_builds_linked_claim_ids() -> None:
    """Claims link back to the rewrite and paragraph, numbered per paragraph."""
    claims = decompose(_synthetic_rewrite(), Method.SENTENCES)
    assert [c.claim_id for c in claims] == [
        "synthetic:discussion|default|1#p1#c1",
        "synthetic:discussion|default|1#p1#c2",
        "synthetic:discussion|default|1#p1#c3",
        "synthetic:discussion|default|1#p2#c1",
    ]
    assert {c.method for c in claims} == {"sentences"}
    assert all(c.synthetic for c in claims)
    assert type(claims[0]).from_record(claims[0].to_record()) == claims[0]


def test_llm_method_with_fake_client_round_trips_additions() -> None:
    """The prompt re-marks additions; the fake's JSON parses into the same claims."""
    client, _ = make_client(ClientKind.FAKE, role="generation", settings=Settings())
    claims = decompose(_synthetic_rewrite(), Method.LLM, client=client)
    assert [(c.text, c.in_addition) for c in claims if c.paragraph_id == "p1"] == [
        ("Synthetic mice lived longer.", False),
        ("Mice are mammals.", True),
        ("The effect may be small.", False),
    ]
    assert claims[0].prompt_version == "decompose_v1"
    assert claims[0].model == "fake-deterministic"
    prompt = client.calls[0].messages[0].content  # type: ignore[attr-defined]
    assert "<added>Mice are mammals.</added>" in prompt


def test_format_rewritten_paragraphs_reinserts_tags() -> None:
    """Additions are re-marked from their offsets."""
    text = format_rewritten_paragraphs(_synthetic_rewrite().paragraphs[:1])
    assert "longer. <added>Mice are mammals.</added> The effect" in text


def test_parse_decomposition_accepts_code_fences() -> None:
    """A JSON object inside a Markdown fence is accepted."""
    payload = {
        "paragraphs": [{"paragraph_id": "p1", "claims": [{"text": " A  b ", "in_addition": False}]}]
    }
    output = f"```json\n{json.dumps(payload)}\n```"
    assert parse_decomposition(output, ["p1"]) == {"p1": [("A b", False)]}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not json", "no JSON object"),
        ('{"paragraphs": {}}', "missing 'paragraphs'"),
        (
            '{"paragraphs": [{"paragraph_id": "x",'
            ' "claims": [{"text": "a", "in_addition": false}]}]}',
            "unknown",
        ),
        ('{"paragraphs": [{"paragraph_id": "p1", "claims": []}]}', "no claims"),
        ('{"paragraphs": [{"paragraph_id": "p1", "claims": [{"text": "a"}]}]}', "in_addition"),
        (
            '{"paragraphs": [{"paragraph_id": "p1",'
            ' "claims": [{"text": "", "in_addition": true}]}]}',
            "no text",
        ),
        ('{"paragraphs": []}', "missing paragraph ids"),
    ],
)
def test_parse_decomposition_contract(payload: str, message: str) -> None:
    """Each contract violation raises DecompositionError with a specific message."""
    with pytest.raises(DecompositionError, match=message):
        parse_decomposition(payload, ["p1"])


def test_invalid_rewrite_or_missing_client_is_refused() -> None:
    """Invalid rewrites are never decomposed; the LLM method needs a client."""
    with pytest.raises(DecompositionError, match="invalid rewrite"):
        decompose(_synthetic_rewrite(valid=False), Method.SENTENCES)
    with pytest.raises(DecompositionError, match="needs a client"):
        decompose(_synthetic_rewrite(), Method.LLM)
    bad = FakeLLMClient(lambda _request: '{"paragraphs": []}')
    with pytest.raises(DecompositionError, match="missing paragraph ids"):
        decompose(_synthetic_rewrite(), Method.LLM, client=bad)
