"""The paragraph-aligned rewrite format: building the input and parsing the output.

Input (in the user prompt)::

    <source id="sec4-p2">Source paragraph text.</source>

Output (expected from the model)::

    <rewrite id="sec4-p2">Plain text. <added>One sentence of context.</added></rewrite>

The parser enforces the alignment contract: exactly one rewrite block per
source paragraph ID, no unknown or duplicate IDs, no empty paragraphs, no
markup other than ``<added>``, no nested or unbalanced ``<added>`` tags, and
at most ``max_added_sentences`` added sentences per paragraph. Violations are
*errors* (the output is invalid and must not be rated); text outside the
blocks and a changed paragraph order are *warnings* (recorded, still usable).
Additions are returned with their character offsets in the clean text, so
claim decomposition and the rubric can tell added content from rewritten
content.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from rbbench.sentences import split_sentences

_BLOCK = re.compile(r'<rewrite\s+id="([^"<>]+)"\s*>(.*?)</rewrite>', re.DOTALL)
_OPEN_BLOCK = re.compile(r"<rewrite\b")
_ADDED = re.compile(r"<added>(.*?)</added>", re.DOTALL)
_TAG = re.compile(r"</?[A-Za-z][^<>]*>")
DEFAULT_MAX_ADDED_SENTENCES = 2


@dataclass(frozen=True, slots=True)
class Addition:
    """One marked addition inside a rewritten paragraph.

    Attributes:
        text: The added text (tags removed).
        start: Offset of the addition in the paragraph's clean text.
        end: End offset (exclusive).
        sentences: How many sentences it contains.
    """

    text: str
    start: int
    end: int
    sentences: int


@dataclass(frozen=True, slots=True)
class RewrittenParagraph:
    """One parsed rewrite block.

    Attributes:
        paragraph_id: The source paragraph ID it rewrites.
        text: The rewritten text with tags removed and whitespace normalised.
        markup: The block's inner text exactly as the model wrote it.
        additions: Marked additions, in order.
    """

    paragraph_id: str
    text: str
    markup: str
    additions: tuple[Addition, ...] = ()

    def marked_text(self) -> str:
        """Return the clean text with ``<added>`` tags re-inserted from the offsets.

        Returns:
            Normalised text in which each addition is wrapped in tags.
        """
        text = self.text
        # Insert from the last addition backwards so earlier offsets stay valid.
        for addition in sorted(self.additions, key=lambda a: a.start, reverse=True):
            text = (
                f"{text[: addition.start]}<added>{text[addition.start : addition.end]}</added>"
                f"{text[addition.end :]}"
            )
        return text

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with the paragraph ID, clean text, raw markup and additions.
        """
        return {
            "paragraph_id": self.paragraph_id,
            "text": self.text,
            "markup": self.markup,
            "additions": [
                {"text": a.text, "start": a.start, "end": a.end, "sentences": a.sentences}
                for a in self.additions
            ],
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> RewrittenParagraph:
        """Build a paragraph from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The paragraph.
        """
        return cls(
            paragraph_id=str(record["paragraph_id"]),
            text=str(record["text"]),
            markup=str(record["markup"]),
            additions=tuple(
                Addition(str(a["text"]), int(a["start"]), int(a["end"]), int(a["sentences"]))
                for a in record["additions"]
            ),
        )


@dataclass(frozen=True, slots=True)
class RewriteParse:
    """The result of parsing one model output.

    Attributes:
        paragraphs: Parsed blocks in source order (only when there are no errors).
        errors: Contract violations; any error makes the output invalid.
        warnings: Tolerated irregularities.
    """

    paragraphs: tuple[RewrittenParagraph, ...]
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = field(default=())

    @property
    def valid(self) -> bool:
        """Whether the output satisfies the alignment contract."""
        return not self.errors


def format_source_paragraphs(paragraphs: Sequence[tuple[str, str]]) -> str:
    """Render source paragraphs for the prompt.

    Args:
        paragraphs: ``(paragraph_id, text)`` pairs in order.

    Returns:
        One ``<source id="...">`` block per paragraph, blank-line separated.
    """
    return "\n\n".join(f'<source id="{pid}">\n{text}\n</source>' for pid, text in paragraphs)


def parse_rewrite(
    output: str,
    expected_ids: Sequence[str],
    *,
    max_added_sentences: int = DEFAULT_MAX_ADDED_SENTENCES,
) -> RewriteParse:
    """Parse and validate a rewrite output.

    Args:
        output: The model's text.
        expected_ids: Source paragraph IDs, in source order.
        max_added_sentences: Upper bound on added sentences per paragraph.

    Returns:
        The parse; ``paragraphs`` is empty whenever there are errors.
    """
    errors: list[str] = []
    warnings: list[str] = []
    blocks = list(_BLOCK.finditer(output))

    # Every opened block must be a complete, well-formed block.
    if len(_OPEN_BLOCK.findall(output)) != len(blocks):
        errors.append("a <rewrite> block is unclosed or malformed")
    outside = _BLOCK.sub("", output).strip()
    if outside:
        warnings.append(f"text outside rewrite blocks was ignored: {outside[:80]!r}")

    # Alignment: each expected ID exactly once, nothing else.
    seen: dict[str, RewrittenParagraph] = {}
    order: list[str] = []
    expected = set(expected_ids)
    for block in blocks:
        paragraph_id, inner = block.group(1).strip(), block.group(2)
        if paragraph_id not in expected:
            errors.append(f"unknown paragraph id {paragraph_id!r}")
            continue
        if paragraph_id in seen:
            errors.append(f"duplicate paragraph id {paragraph_id!r}")
            continue
        paragraph, problems = _parse_block(paragraph_id, inner, max_added_sentences)
        errors.extend(problems)
        seen[paragraph_id] = paragraph
        order.append(paragraph_id)
    errors.extend(f"missing paragraph id {pid!r}" for pid in expected_ids if pid not in seen)
    if not errors and order != list(expected_ids):
        warnings.append("rewrite blocks are not in source order")

    paragraphs = () if errors else tuple(seen[pid] for pid in expected_ids)
    return RewriteParse(paragraphs, tuple(errors), tuple(warnings))


def _parse_block(
    paragraph_id: str, inner: str, max_added_sentences: int
) -> tuple[RewrittenParagraph, list[str]]:
    """Parse one block's inner text into clean text and additions.

    Args:
        paragraph_id: The block's ID.
        inner: The text between the block tags.
        max_added_sentences: Upper bound on added sentences.

    Returns:
        The paragraph and any errors found in it.
    """
    errors: list[str] = []
    # Remove each addition's tags while recording where its text lands.
    clean_parts: list[str] = []
    additions: list[Addition] = []
    cursor = 0
    position = 0
    for match in _ADDED.finditer(inner):
        before = _normalise(inner[cursor : match.start()], leading=not clean_parts)
        clean_parts.append(before)
        position += len(before)
        added = " ".join(match.group(1).split())
        if "<added>" in match.group(1):
            errors.append(f"{paragraph_id}: nested <added> tags")
        sentences = len(split_sentences(added))
        additions.append(Addition(added, position, position + len(added), sentences))
        clean_parts.append(added)
        position += len(added)
        cursor = match.end()
    clean_parts.append(_normalise(inner[cursor:], leading=not clean_parts))
    text = "".join(clean_parts).rstrip()

    # Anything tag-like left over is a contract violation.
    leftover = _TAG.findall(_ADDED.sub("", inner))
    if leftover:
        errors.append(f"{paragraph_id}: unexpected markup {sorted(set(leftover))}")
    if not text:
        errors.append(f"{paragraph_id}: empty rewrite")
    if any(not a.text for a in additions):
        errors.append(f"{paragraph_id}: empty <added> span")
    total_added = sum(a.sentences for a in additions)
    if total_added > max_added_sentences:
        errors.append(
            f"{paragraph_id}: {total_added} added sentences (at most {max_added_sentences})"
        )
    return RewrittenParagraph(paragraph_id, text, inner.strip(), tuple(additions)), errors


def _normalise(chunk: str, *, leading: bool) -> str:
    """Collapse whitespace in a chunk of clean text, keeping word separation.

    Args:
        chunk: Raw text between tags.
        leading: True for the paragraph's first chunk (leading space dropped).

    Returns:
        The chunk with internal whitespace collapsed to single spaces.
    """
    if not chunk:
        return ""
    collapsed = " ".join(chunk.split())
    if not collapsed:
        return "" if leading else " "
    prefix = "" if leading or not chunk[0].isspace() else " "
    suffix = " " if chunk[-1].isspace() else ""
    return prefix + collapsed + suffix
