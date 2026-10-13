"""Tests of the sentence splitter, the prompt loader and the committed prompt files."""

from __future__ import annotations

from pathlib import Path

import pytest

from rbbench.paths import PROMPTS_DIR
from rbbench.prompts import PromptError, load_prompt, parse_prompt
from rbbench.sentences import sentence_spans, split_sentences


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Mice lost 3.5 g (n = 12; p < 0.01). This was shown by Smith et al. in Fig. 2B.",
            ["Mice lost 3.5 g (n = 12; p < 0.01).", "This was shown by Smith et al. in Fig. 2B."],
        ),
        ("E. coli grew. A. viteae did not.", ["E. coli grew.", "A. viteae did not."]),
        ("The U.S. trial ended. It was small.", ["The U.S. trial ended.", "It was small."]),
        (
            "Results (see Fig. 3. Left) held! 40% responded.",
            ["Results (see Fig. 3. Left) held!", "40% responded."],
        ),
        ("Is it? “Yes,” she said.", ["Is it?", "“Yes,” she said."]),
        ("e.g. this stays whole. Next.", ["e.g. this stays whole.", "Next."]),
        ("   ", []),
    ],
)
def test_split_sentences(text: str, expected: list[str]) -> None:
    """Boundaries respect abbreviations, initials, decimals and brackets."""
    assert split_sentences(text) == expected


def test_sentence_spans_point_into_the_text() -> None:
    """Spans are offsets into the original text, stripped of whitespace."""
    text = "  One here.  Two there. "
    assert [text[a:b] for a, b in sentence_spans(text)] == ["One here.", "Two there."]


def test_committed_prompts_load_and_name_their_placeholders() -> None:
    """Every committed prompt parses, matches its file name and uses known placeholders."""
    expected = {
        "rewrite_v1": {"title", "source_paragraphs"},
        "decompose_v1": {"rewritten_paragraphs"},
        "judge_v1": {"unit_description", "codes", "response_schema", "item"},
    }
    assert {p.stem for p in PROMPTS_DIR.glob("*.md")} == set(expected)
    for version, placeholders in expected.items():
        prompt = load_prompt(version)
        assert prompt.version == version
        assert prompt.placeholders == placeholders
        assert len(prompt.sha256) == 64


def test_rewrite_prompt_asks_for_marked_additions_without_be_accurate() -> None:
    """The rewrite prompt defines the <added> markup and avoids 'be accurate'.

    Peters & Chin-Yee (2025) found that asking for accuracy increased
    overgeneralisation, so the prompt states operational rules instead.
    """
    prompt = load_prompt("rewrite_v1")
    assert "<added>" in prompt.system
    assert '<rewrite id="ID">' in prompt.system
    assert "be accurate" not in prompt.system.lower()


def test_render_fills_placeholders_and_rejects_mismatches() -> None:
    """Rendering needs exactly the template's placeholders."""
    prompt = parse_prompt("---\nversion: t_v1\n---\n## System\nS {{a}}\n## User\nU {{b}}\n")
    assert prompt.render(a="1", b="2") == ("S 1", "U 2")
    assert prompt.max_tokens == 4096
    with pytest.raises(PromptError, match="missing"):
        prompt.render(a="1")
    with pytest.raises(PromptError, match="unused"):
        prompt.render(a="1", b="2", c="3")


@pytest.mark.parametrize(
    "text",
    [
        "## System\nS\n## User\nU\n",
        "---\nversion: 3\n---\n## System\nS\n## User\nU\n",
        "---\nversion: v\n---\n## User\nU\n## System\nS\n",
        "---\nversion: v\n---\n## System\n\n## User\nU\n",
        "---\nversion: v\nmax_tokens: -1\n---\n## System\nS\n## User\nU\n",
    ],
)
def test_malformed_prompts_are_rejected(text: str) -> None:
    """Missing front matter, bad version, wrong order, empty section, bad max_tokens."""
    with pytest.raises(PromptError):
        parse_prompt(text)


def test_load_prompt_checks_declared_version(tmp_path: Path) -> None:
    """A file whose front matter names another version is refused."""
    path = tmp_path / "x_v1.md"
    path.write_text("---\nversion: x_v2\n---\n## System\nS\n## User\nU\n", encoding="utf-8")
    with pytest.raises(PromptError, match="expected 'x_v1'"):
        load_prompt("x_v1", tmp_path)
