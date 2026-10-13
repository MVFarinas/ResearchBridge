"""The rewrite harness: passages x matrix arms -> rewrite records with full provenance.

Each record (one JSON line) holds the passage, the arm, the requested and the
reported model, the prompt version and SHA-256, the temperature, a UTC
timestamp, token counts, whether the output was synthetic, the parse result
(valid or the list of errors), and the raw output for audit. A failed call is
recorded too, with its error, so a run never silently drops a cell of the
matrix.

Before any call, every passage is re-checked against the §1.1 gate
(:func:`rbbench.ingest.require_rewritable`): the owner may edit
``passages.jsonl``, so a passage over a paragraph or paper the ingest gate
refused stops the whole run and nothing is sent.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rbbench.ingest import Passage, SourceUnit, passage_units, require_rewritable
from rbbench.jsonl import utc_now_iso
from rbbench.prompts import PromptTemplate, load_prompt
from rbbench.rewrite.markup import (
    DEFAULT_MAX_ADDED_SENTENCES,
    RewrittenParagraph,
    format_source_paragraphs,
    parse_rewrite,
)
from rbcore.llm import LLMClient, LLMError, LLMRequest


class MatrixError(ValueError):
    """Raised when the rewrite matrix config is invalid."""


@dataclass(frozen=True, slots=True)
class Arm:
    """One cell of the configuration matrix.

    Attributes:
        name: Arm name, e.g. "temperature-0".
        temperature: Sampling temperature, or None for the model default.
    """

    name: str
    temperature: float | None


@dataclass(frozen=True, slots=True)
class RewriteMatrix:
    """The rewrite configuration matrix.

    Attributes:
        version: Matrix version.
        prompt: Prompt version to use.
        arms: The arms.
        max_added_sentences: Parser limit on added sentences per paragraph.
    """

    version: str
    prompt: str
    arms: tuple[Arm, ...]
    max_added_sentences: int = DEFAULT_MAX_ADDED_SENTENCES


def load_matrix(path: Path) -> RewriteMatrix:
    """Load and validate a matrix config.

    Args:
        path: The YAML file.

    Returns:
        The matrix.

    Raises:
        MatrixError: If arms are missing, duplicated or have a bad temperature.
    """
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    try:
        arms = tuple(
            Arm(
                str(a["name"]),
                None if a.get("temperature") is None else float(a["temperature"]),
            )
            for a in raw["arms"]
        )
        matrix = RewriteMatrix(
            version=str(raw["version"]),
            prompt=str(raw["prompt"]),
            arms=arms,
            max_added_sentences=int(raw.get("max_added_sentences", DEFAULT_MAX_ADDED_SENTENCES)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MatrixError(f"{path}: {exc}") from exc
    names = [arm.name for arm in matrix.arms]
    if not names or len(names) != len(set(names)):
        raise MatrixError(f"{path}: arms must be non-empty with unique names")
    if any(a.temperature is not None and not 0.0 <= a.temperature <= 1.0 for a in matrix.arms):
        raise MatrixError(f"{path}: temperature must be between 0 and 1, or null")
    return matrix


@dataclass(frozen=True, slots=True)
class RewriteRecord:
    """One rewrite attempt and its provenance.

    Attributes:
        rewrite_id: ``<passage_id>|<arm>|<n>``.
        passage_id: The passage.
        paper_key: The paper.
        arm: Matrix arm name.
        requested_model: Model asked for.
        model: Model that answered (as reported), or "" on failure.
        prompt_version: Prompt version.
        prompt_sha256: SHA-256 of the prompt file.
        temperature: Temperature sent, or None for the default.
        timestamp: UTC time of the call.
        synthetic: True for fake-client output.
        valid: Whether the output passed the alignment contract.
        errors: Parse errors or the call error.
        warnings: Parse warnings.
        paragraphs: Parsed paragraphs (empty unless valid).
        source: The source paragraphs as ``(paragraph_id, text)``.
        raw_output: The model's text.
        stop_reason: The API stop reason.
        input_tokens: Prompt tokens.
        output_tokens: Output tokens.
    """

    rewrite_id: str
    passage_id: str
    paper_key: str
    arm: str
    requested_model: str
    model: str
    prompt_version: str
    prompt_sha256: str
    temperature: float | None
    timestamp: str
    synthetic: bool
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    paragraphs: tuple[RewrittenParagraph, ...]
    source: tuple[tuple[str, str], ...]
    raw_output: str
    stop_reason: str | None
    input_tokens: int
    output_tokens: int

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with ``record_type`` "rewrite".
        """
        return {
            "record_type": "rewrite",
            "rewrite_id": self.rewrite_id,
            "passage_id": self.passage_id,
            "paper_key": self.paper_key,
            "arm": self.arm,
            "requested_model": self.requested_model,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "prompt_sha256": self.prompt_sha256,
            "temperature": self.temperature,
            "timestamp": self.timestamp,
            "synthetic": self.synthetic,
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "paragraphs": [p.to_record() for p in self.paragraphs],
            "source": [{"paragraph_id": pid, "text": text} for pid, text in self.source],
            "raw_output": self.raw_output,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> RewriteRecord:
        """Build a record from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The record.
        """
        return cls(
            rewrite_id=str(record["rewrite_id"]),
            passage_id=str(record["passage_id"]),
            paper_key=str(record["paper_key"]),
            arm=str(record["arm"]),
            requested_model=str(record["requested_model"]),
            model=str(record["model"]),
            prompt_version=str(record["prompt_version"]),
            prompt_sha256=str(record["prompt_sha256"]),
            temperature=record["temperature"],
            timestamp=str(record["timestamp"]),
            synthetic=bool(record["synthetic"]),
            valid=bool(record["valid"]),
            errors=tuple(record["errors"]),
            warnings=tuple(record["warnings"]),
            paragraphs=tuple(RewrittenParagraph.from_record(p) for p in record["paragraphs"]),
            source=tuple((str(s["paragraph_id"]), str(s["text"])) for s in record["source"]),
            raw_output=str(record["raw_output"]),
            stop_reason=record.get("stop_reason"),
            input_tokens=int(record["input_tokens"]),
            output_tokens=int(record["output_tokens"]),
        )


def run_rewrites(
    passages: Sequence[Passage],
    units: dict[str, SourceUnit],
    titles: dict[str, str],
    matrix: RewriteMatrix,
    client: LLMClient,
    *,
    requested_model: str,
    repeats: int = 1,
    prompt: PromptTemplate | None = None,
    progress: Callable[[str], None] | None = None,
    usable_papers: Collection[str] | None = None,
) -> list[RewriteRecord]:
    """Rewrite every passage once per arm (and per repeat).

    Args:
        passages: Passages to rewrite.
        units: Units by unit ID.
        titles: Paper titles by paper key (for the prompt).
        matrix: The configuration matrix.
        client: The LLM client (fake in tests and dry runs).
        requested_model: The model ID requested (recorded).
        repeats: Rewrites per (passage, arm), for run-to-run variation.
        prompt: The prompt; loaded from the matrix's version when None.
        progress: Optional callback for one-line progress messages.
        usable_papers: Keys of the papers the ingest gate found usable; when
            given, a passage of any other paper is refused too.

    Returns:
        One record per attempt, including failed ones.

    Raises:
        rbbench.ingest.LicenceGateError: If any passage includes a paragraph
            that may not be rewritten, has no unit, or belongs to an unusable
            paper. Raised before any call is made.
    """
    # The §1.1 gate again, for the whole batch, before a single call.
    require_rewritable(passages, units, usable_papers)

    template = prompt or load_prompt(matrix.prompt)
    report = progress or (lambda _message: None)
    records: list[RewriteRecord] = []
    for passage in passages:
        # One rendered prompt per passage, shared by every arm and repeat.
        source = tuple((u.paragraph_id, u.text) for u in passage_units(passage, units))
        system, user = template.render(
            title=titles.get(passage.paper_key, ""),
            source_paragraphs=format_source_paragraphs(source),
        )
        # Every arm x repeat is one cell of the matrix, recorded even when it fails.
        for arm in matrix.arms:
            for repeat in range(1, repeats + 1):
                request = LLMRequest.from_prompt(
                    user,
                    system=system,
                    max_tokens=template.max_tokens,
                    temperature=arm.temperature,
                    prompt_version=template.version,
                )
                records.append(
                    _attempt(
                        f"{passage.passage_id}|{arm.name}|{repeat}",
                        passage,
                        arm,
                        source,
                        request,
                        client,
                        requested_model,
                        template,
                        matrix.max_added_sentences,
                    )
                )
                report(f"{records[-1].rewrite_id}: {'valid' if records[-1].valid else 'INVALID'}")
    return records


def _attempt(
    rewrite_id: str,
    passage: Passage,
    arm: Arm,
    source: tuple[tuple[str, str], ...],
    request: LLMRequest,
    client: LLMClient,
    requested_model: str,
    template: PromptTemplate,
    max_added_sentences: int,
) -> RewriteRecord:
    """Make one call and turn its outcome into a record.

    Args:
        rewrite_id: The record ID.
        passage: The passage.
        arm: The matrix arm.
        source: The source paragraphs.
        request: The request to send.
        client: The LLM client.
        requested_model: Model asked for.
        template: The prompt (for provenance).
        max_added_sentences: Parser limit.

    Returns:
        The record; a failed call yields an invalid record with the error.
    """
    timestamp = utc_now_iso()

    def record(**outcome: Any) -> RewriteRecord:
        """Combine the attempt's fixed provenance with its outcome."""
        return RewriteRecord(
            rewrite_id=rewrite_id,
            passage_id=passage.passage_id,
            paper_key=passage.paper_key,
            arm=arm.name,
            requested_model=requested_model,
            prompt_version=template.version,
            prompt_sha256=template.sha256,
            temperature=arm.temperature,
            timestamp=timestamp,
            source=source,
            **outcome,
        )

    try:
        response = client.complete(request)
    except LLMError as exc:
        # A failed cell is recorded, not dropped, so the matrix stays complete.
        return record(
            model="",
            synthetic=False,
            valid=False,
            errors=(f"call failed: {exc}",),
            warnings=(),
            paragraphs=(),
            raw_output="",
            stop_reason=None,
            input_tokens=0,
            output_tokens=0,
        )
    # Validate the alignment contract; a truncated answer is never valid.
    parsed = parse_rewrite(
        response.text, [pid for pid, _ in source], max_added_sentences=max_added_sentences
    )
    errors = list(parsed.errors)
    if response.stop_reason == "max_tokens":
        errors.append("output truncated (stop_reason max_tokens)")
    return record(
        model=response.model,
        synthetic=response.synthetic,
        valid=not errors,
        errors=tuple(errors),
        warnings=parsed.warnings,
        paragraphs=parsed.paragraphs if not errors else (),
        raw_output=response.text,
        stop_reason=response.stop_reason,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
