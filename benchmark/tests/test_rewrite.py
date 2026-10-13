"""Tests of the rewrite markup parser, the matrix config and the harness.

Model outputs here are SYNTHETIC strings written for the tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rbbench.clients import ClientKind, LiveCallsNotAllowedError, make_client
from rbbench.fakes import SYNTHETIC_ADDITION, SYNTHETIC_REWRITE_PREFIX
from rbbench.ingest import Passage, SourceUnit
from rbbench.paths import CONFIG_DIR
from rbbench.rewrite.harness import MatrixError, load_matrix, run_rewrites
from rbbench.rewrite.markup import format_source_paragraphs, parse_rewrite
from rbcore.config import ConfigError, Settings
from rbcore.llm import FakeLLMClient, LLMError, LLMRequest, LLMResponse

IDS = ["sec1-p1", "sec1-p2"]


def test_valid_output_yields_clean_text_and_addition_offsets() -> None:
    """Additions are extracted with offsets into the tag-free text."""
    output = (
        '<rewrite id="sec1-p1">Mice  lived longer. <added>Mice are\nmammals.</added> '
        "The effect was small.</rewrite>\n"
        '<rewrite id="sec1-p2">No change was seen.</rewrite>'
    )
    parsed = parse_rewrite(output, IDS)
    assert parsed.valid, parsed.errors
    first = parsed.paragraphs[0]
    assert first.text == "Mice lived longer. Mice are mammals. The effect was small."
    (addition,) = first.additions
    assert addition.text == "Mice are mammals."
    assert first.text[addition.start : addition.end] == "Mice are mammals."
    assert addition.sentences == 1
    assert parsed.paragraphs[1].additions == ()


def test_paragraph_starting_with_an_addition_keeps_offsets() -> None:
    """An addition at the very start has offset 0."""
    parsed = parse_rewrite('<rewrite id="a"><added>Context.</added> Finding.</rewrite>', ["a"])
    paragraph = parsed.paragraphs[0]
    assert paragraph.text == "Context. Finding."
    assert (paragraph.additions[0].start, paragraph.additions[0].end) == (0, 8)


@pytest.mark.parametrize(
    ("output", "error"),
    [
        ('<rewrite id="sec1-p1">A.</rewrite>', "missing paragraph id 'sec1-p2'"),
        (
            '<rewrite id="sec1-p1">A.</rewrite><rewrite id="sec1-p1">B.</rewrite>'
            '<rewrite id="sec1-p2">C.</rewrite>',
            "duplicate paragraph id 'sec1-p1'",
        ),
        (
            '<rewrite id="sec1-p1">A.</rewrite><rewrite id="sec1-p2">B.</rewrite>'
            '<rewrite id="sec9-p9">C.</rewrite>',
            "unknown paragraph id 'sec9-p9'",
        ),
        ('<rewrite id="sec1-p1"> </rewrite><rewrite id="sec1-p2">B.</rewrite>', "empty rewrite"),
        (
            '<rewrite id="sec1-p1">A <b>bold</b>.</rewrite><rewrite id="sec1-p2">B.</rewrite>',
            "unexpected markup",
        ),
        (
            '<rewrite id="sec1-p1">A. <added>One. Two. Three.</added></rewrite>'
            '<rewrite id="sec1-p2">B.</rewrite>',
            "3 added sentences (at most 2)",
        ),
        (
            '<rewrite id="sec1-p1">A. <added>Open only.</rewrite>'
            '<rewrite id="sec1-p2">B.</rewrite>',
            "unexpected markup",
        ),
        ('<rewrite id="sec1-p1">A.</rewrite><rewrite id="sec1-p2">B.', "unclosed"),
    ],
)
def test_contract_violations_are_errors(output: str, error: str) -> None:
    """Each violation of the alignment contract invalidates the output."""
    parsed = parse_rewrite(output, IDS)
    assert not parsed.valid
    assert parsed.paragraphs == ()
    assert any(error in e for e in parsed.errors), parsed.errors


def test_preface_and_reordering_are_warnings_only() -> None:
    """Text outside blocks and a changed order are tolerated but recorded."""
    output = 'Here you go:\n<rewrite id="sec1-p2">B.</rewrite><rewrite id="sec1-p1">A.</rewrite>'
    parsed = parse_rewrite(output, IDS)
    assert parsed.valid
    assert [p.paragraph_id for p in parsed.paragraphs] == IDS
    assert len(parsed.warnings) == 2


def test_less_than_sign_in_text_is_not_markup() -> None:
    """Statistics such as 'p < 0.05' are not mistaken for tags."""
    parsed = parse_rewrite('<rewrite id="a">The result held (p < 0.05).</rewrite>', ["a"])
    assert parsed.valid


def test_format_source_paragraphs() -> None:
    """Source blocks carry the paragraph IDs the parser will expect back."""
    assert format_source_paragraphs([("a", "Text.")]) == '<source id="a">\nText.\n</source>'


def test_committed_matrix_has_temperature_zero_and_default_arms() -> None:
    """rewrite_matrix_v1 tests temperature 0 against the model default."""
    matrix = load_matrix(CONFIG_DIR / "rewrite_matrix_v1.yaml")
    assert matrix.prompt == "rewrite_v1"
    assert [(a.name, a.temperature) for a in matrix.arms] == [
        ("temperature-0", 0.0),
        ("default", None),
    ]


@pytest.mark.parametrize(
    "arms",
    [
        "[]",
        "[{name: a, temperature: 0}, {name: a, temperature: null}]",
        "[{name: a, temperature: 1.5}]",
    ],
)
def test_invalid_matrix_is_rejected(tmp_path: Path, arms: str) -> None:
    """Empty arms, duplicate names and out-of-range temperatures are refused."""
    path = tmp_path / "m.yaml"
    path.write_text(f"version: m\nprompt: rewrite_v1\narms: {arms}\n", encoding="utf-8")
    with pytest.raises(MatrixError):
        load_matrix(path)


def _synthetic_passage() -> tuple[Passage, dict[str, SourceUnit]]:
    """A two-paragraph SYNTHETIC passage."""
    units = {
        f"synthetic-paper#{pid}": SourceUnit(
            unit_id=f"synthetic-paper#{pid}",
            paper_key="synthetic-paper",
            paragraph_id=pid,
            section_path=("Discussion",),
            kind="p",
            text=text,
            words=len(text.split()),
            can_rewrite=True,
        )
        for pid, text in [
            ("sec1-p1", "Synthetic finding one was seen. It may matter."),
            ("sec1-p2", "Synthetic finding two was not significant."),
        ]
    }
    passage = Passage("synthetic-paper:discussion", "synthetic-paper", tuple(IDS), 13, "discussion")
    return passage, units


def test_harness_runs_every_arm_with_full_provenance() -> None:
    """The fake client yields one valid, synthetic, fully attributed record per arm."""
    passage, units = _synthetic_passage()
    matrix = load_matrix(CONFIG_DIR / "rewrite_matrix_v1.yaml")
    client, requested = make_client(ClientKind.FAKE, role="generation", settings=Settings())
    records = run_rewrites(
        [passage],
        units,
        {"synthetic-paper": "A synthetic title"},
        matrix,
        client,
        requested_model=requested,
    )
    assert [r.arm for r in records] == ["temperature-0", "default"]
    for record in records:
        assert record.valid, record.errors
        assert record.synthetic
        assert record.prompt_version == "rewrite_v1"
        assert len(record.prompt_sha256) == 64
        assert record.timestamp.endswith("Z")
        first = record.paragraphs[0]
        assert first.text.startswith(SYNTHETIC_REWRITE_PREFIX)
        assert first.additions[0].text == SYNTHETIC_ADDITION
    assert [r.temperature for r in records] == [0.0, None]
    # The temperature reached the client exactly as configured.
    assert [c.temperature for c in client.calls] == [0.0, None]  # type: ignore[attr-defined]
    assert "A synthetic title" in client.calls[0].messages[0].content  # type: ignore[attr-defined]
    round_trip = type(records[0]).from_record(records[0].to_record())
    assert round_trip == records[0]


def test_harness_records_failed_and_invalid_calls() -> None:
    """A failing call and a malformed output are recorded as invalid, not dropped."""
    passage, units = _synthetic_passage()
    matrix = load_matrix(CONFIG_DIR / "rewrite_matrix_v1.yaml")

    class FailingOnce:
        """A client whose first call raises and second returns a bad output."""

        def __init__(self) -> None:
            """Start with no calls."""
            self.count = 0

        def complete(self, request: LLMRequest) -> LLMResponse:
            """Fail first, then answer with an unaligned output."""
            self.count += 1
            if self.count == 1:
                raise LLMError("synthetic HTTP 400: temperature not supported")
            return LLMResponse('<rewrite id="sec1-p1">Only one.</rewrite>', "m", "end_turn")

    records = run_rewrites([passage], units, {}, matrix, FailingOnce(), requested_model="m")
    assert [r.valid for r in records] == [False, False]
    assert "call failed" in records[0].errors[0]
    assert any("missing paragraph id" in e for e in records[1].errors)
    assert records[1].raw_output.startswith("<rewrite")


def test_truncated_output_is_invalid() -> None:
    """stop_reason max_tokens invalidates an otherwise parseable output."""
    passage, units = _synthetic_passage()
    matrix = load_matrix(CONFIG_DIR / "rewrite_matrix_v1.yaml")
    text = '<rewrite id="sec1-p1">A.</rewrite><rewrite id="sec1-p2">B.</rewrite>'
    client = FakeLLMClient(lambda _request: text)

    class Truncating:
        """Wraps the fake and reports truncation."""

        def complete(self, request: LLMRequest) -> LLMResponse:
            """Return the fake response marked as truncated."""
            response = client.complete(request)
            return LLMResponse(response.text, response.model, "max_tokens", synthetic=True)

    records = run_rewrites([passage], units, {}, matrix, Truncating(), requested_model="m")
    assert all("truncated" in r.errors[-1] for r in records)


def test_real_client_requires_live_flag_and_key() -> None:
    """The Anthropic client is never built without --live, and needs a key and model."""
    settings = Settings(generation_model="model-from-config")
    with pytest.raises(LiveCallsNotAllowedError):
        make_client(ClientKind.ANTHROPIC, role="generation", settings=settings)
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        make_client(ClientKind.ANTHROPIC, role="generation", settings=settings, live=True)
    same = Settings(anthropic_api_key="k", generation_model="m", judge_model="m")
    with pytest.raises(ConfigError, match="differ"):
        make_client(ClientKind.ANTHROPIC, role="judge", settings=same, live=True)
