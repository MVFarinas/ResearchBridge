"""Claim decomposition: each rewritten paragraph -> atomic claims linked to its paragraph ID.

Two methods, recorded on every claim:

* ``llm``: the versioned prompt (``prompts/decompose_v1.md``) and a strict
  JSON parser. A failed parse is reported, never silently replaced.
* ``sentences``: a deterministic fallback, one claim per sentence of the
  rewritten paragraph (:mod:`rbbench.sentences`), used in tests and the dry
  run. Coarser than atomic claims; real benchmark runs should use ``llm`` and
  have a rater spot-check the split (the rater guide asks raters to flag
  non-claims).

A claim from inside a marked addition is flagged ``in_addition`` so the
rubric can classify added content separately.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from rbbench.prompts import PromptTemplate, load_prompt
from rbbench.rewrite.harness import RewriteRecord
from rbbench.rewrite.markup import RewrittenParagraph
from rbbench.sentences import sentence_spans
from rbcore.llm import LLMClient, LLMError, LLMRequest

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


class Method(StrEnum):
    """How claims were produced."""

    LLM = "llm"
    SENTENCES = "sentences"


class DecompositionError(ValueError):
    """Raised when a decomposition output cannot be parsed or breaks the contract."""


@dataclass(frozen=True, slots=True)
class Claim:
    """One atomic claim.

    Attributes:
        claim_id: ``<rewrite_id>#<paragraph_id>#c<n>``.
        rewrite_id: The rewrite it comes from.
        passage_id: The passage.
        paper_key: The paper.
        paragraph_id: The rewritten (and source) paragraph it belongs to.
        index: 1-based position within the paragraph.
        text: The claim.
        in_addition: Whether it comes from a marked addition.
        method: "llm" or "sentences".
        model: Decomposition model ("" for the sentence method).
        prompt_version: Decomposition prompt version ("" for sentences).
        synthetic: True when produced from synthetic input or a fake client.
    """

    claim_id: str
    rewrite_id: str
    passage_id: str
    paper_key: str
    paragraph_id: str
    index: int
    text: str
    in_addition: bool
    method: str
    model: str
    prompt_version: str
    synthetic: bool

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with ``record_type`` "claim".
        """
        return {"record_type": "claim", **{k: getattr(self, k) for k in self.__slots__}}

    @classmethod
    def from_record(cls, record: dict[str, Any]) -> Claim:
        """Build a claim from its JSON form.

        Args:
            record: A dict written by :meth:`to_record`.

        Returns:
            The claim.
        """
        return cls(**{k: record[k] for k in cls.__slots__})


def paragraph_unit_id(rewrite_id: str, paragraph_id: str) -> str:
    """Return the unit ID of a rewritten paragraph (for paragraph-level codes).

    Args:
        rewrite_id: The rewrite.
        paragraph_id: The paragraph.

    Returns:
        ``<rewrite_id>#<paragraph_id>``.
    """
    return f"{rewrite_id}#{paragraph_id}"


def format_rewritten_paragraphs(paragraphs: Sequence[RewrittenParagraph]) -> str:
    """Render rewritten paragraphs, additions re-marked, for the decomposition prompt.

    Args:
        paragraphs: Parsed rewritten paragraphs.

    Returns:
        One ``<rewritten id="...">`` block per paragraph.
    """
    blocks = [
        f'<rewritten id="{p.paragraph_id}">\n{p.marked_text()}\n</rewritten>' for p in paragraphs
    ]
    return "\n\n".join(blocks)


def parse_decomposition(
    output: str, expected_ids: Sequence[str]
) -> dict[str, list[tuple[str, bool]]]:
    """Parse and validate a decomposition output.

    Args:
        output: The model's text (a JSON object, optionally in a code fence).
        expected_ids: Paragraph IDs that must each appear exactly once.

    Returns:
        Paragraph ID -> list of ``(claim_text, in_addition)``.

    Raises:
        DecompositionError: If the JSON is invalid or breaks the contract.
    """
    text = _FENCE.sub("", output.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise DecompositionError("no JSON object in the output")
    try:
        data: Any = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DecompositionError(f"invalid JSON: {exc}") from exc
    paragraphs = data.get("paragraphs") if isinstance(data, dict) else None
    if not isinstance(paragraphs, list):
        raise DecompositionError("missing 'paragraphs' list")

    result: dict[str, list[tuple[str, bool]]] = {}
    for item in paragraphs:
        paragraph_id = item.get("paragraph_id") if isinstance(item, dict) else None
        claims = item.get("claims") if isinstance(item, dict) else None
        if not isinstance(paragraph_id, str) or paragraph_id not in expected_ids:
            raise DecompositionError(f"unknown paragraph id {paragraph_id!r}")
        if paragraph_id in result:
            raise DecompositionError(f"duplicate paragraph id {paragraph_id!r}")
        if not isinstance(claims, list) or not claims:
            raise DecompositionError(f"{paragraph_id}: no claims")
        parsed: list[tuple[str, bool]] = []
        for claim in claims:
            claim_text = claim.get("text") if isinstance(claim, dict) else None
            in_addition = claim.get("in_addition") if isinstance(claim, dict) else None
            if not isinstance(claim_text, str) or not claim_text.strip():
                raise DecompositionError(f"{paragraph_id}: a claim has no text")
            if not isinstance(in_addition, bool):
                raise DecompositionError(f"{paragraph_id}: in_addition must be true or false")
            parsed.append((" ".join(claim_text.split()), in_addition))
        result[paragraph_id] = parsed
    missing = [pid for pid in expected_ids if pid not in result]
    if missing:
        raise DecompositionError(f"missing paragraph ids {missing}")
    return result


def sentence_claims(paragraph: RewrittenParagraph) -> list[tuple[str, bool]]:
    """Split a rewritten paragraph into one claim per sentence.

    A sentence counts as from an addition when at least half of its
    characters lie inside marked additions.

    Args:
        paragraph: The rewritten paragraph.

    Returns:
        ``(claim_text, in_addition)`` pairs in order.
    """
    claims = []
    for start, end in sentence_spans(paragraph.text):
        inside = sum(max(0, min(end, a.end) - max(start, a.start)) for a in paragraph.additions)
        claims.append((paragraph.text[start:end], inside * 2 >= end - start))
    return claims


def decompose(
    rewrite: RewriteRecord,
    method: Method,
    *,
    client: LLMClient | None = None,
    prompt: PromptTemplate | None = None,
) -> list[Claim]:
    """Decompose one valid rewrite into claims.

    Args:
        rewrite: A valid rewrite record.
        method: LLM or sentence fallback.
        client: Required for the LLM method.
        prompt: Decomposition prompt; ``decompose_v1`` when None.

    Returns:
        Claims in paragraph order.

    Raises:
        DecompositionError: If the rewrite is invalid, the client is missing,
            the call fails, or the output breaks the contract.
    """
    if not rewrite.valid:
        raise DecompositionError(f"{rewrite.rewrite_id}: cannot decompose an invalid rewrite")
    ids = [p.paragraph_id for p in rewrite.paragraphs]
    model = prompt_version = ""
    synthetic = rewrite.synthetic

    # Produce (text, in_addition) per paragraph by the chosen method.
    if method is Method.SENTENCES:
        by_paragraph = {p.paragraph_id: sentence_claims(p) for p in rewrite.paragraphs}
    else:
        if client is None:
            raise DecompositionError("the llm method needs a client")
        template = prompt or load_prompt("decompose_v1")
        system, user = template.render(
            rewritten_paragraphs=format_rewritten_paragraphs(rewrite.paragraphs)
        )
        request = LLMRequest.from_prompt(
            user, system=system, max_tokens=template.max_tokens, prompt_version=template.version
        )
        try:
            response = client.complete(request)
        except LLMError as exc:
            raise DecompositionError(f"{rewrite.rewrite_id}: call failed: {exc}") from exc
        by_paragraph = parse_decomposition(response.text, ids)
        model, prompt_version = response.model, template.version
        synthetic = synthetic or response.synthetic

    return [
        Claim(
            claim_id=f"{paragraph_unit_id(rewrite.rewrite_id, paragraph_id)}#c{index}",
            rewrite_id=rewrite.rewrite_id,
            passage_id=rewrite.passage_id,
            paper_key=rewrite.paper_key,
            paragraph_id=paragraph_id,
            index=index,
            text=text,
            in_addition=in_addition,
            method=method.value,
            model=model,
            prompt_version=prompt_version,
            synthetic=synthetic,
        )
        for paragraph_id in ids
        for index, (text, in_addition) in enumerate(by_paragraph[paragraph_id], start=1)
    ]
