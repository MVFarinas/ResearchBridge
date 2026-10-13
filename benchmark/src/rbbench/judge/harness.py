"""The LLM judge: one request per claim (or paragraph), labelled with the rubric.

The rubric's questions and allowed values are rendered into the versioned
prompt (``prompts/judge_v1.md``), so the judge and the human raters answer
exactly the same codes. The output is strict JSON, validated against the
rubric; an invalid output is recorded with its error and never guessed.
Judge records convert to :class:`rbbench.ratings.Rating` with the judge as
the rater, so judge-vs-human agreement reuses the agreement statistics.

decisions.md §1.4: the judge must not be the model that generated the
rewrite. :func:`judge_items` refuses a judge whose model equals the
rewrite's model (fake clients excepted).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from rbbench.claims import Claim, paragraph_unit_id
from rbbench.jsonl import utc_now_iso
from rbbench.prompts import PromptTemplate, load_prompt
from rbbench.ratings import Rating
from rbbench.rewrite.harness import RewriteRecord
from rbbench.rubric import Rubric, RubricCode, Unit
from rbcore.llm import FAKE_MODEL, LLMClient, LLMError, LLMRequest

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")

UNIT_DESCRIPTIONS = {
    Unit.CLAIM: (
        "The item to judge is one atomic claim taken from the rewritten paragraph. "
        "Answer every question about that claim only."
    ),
    Unit.PARAGRAPH: (
        "The item to judge is the rewritten paragraph as a whole, compared with its aligned "
        "source paragraph."
    ),
}


class JudgeError(ValueError):
    """Raised when a judge output cannot be parsed or does not fit the rubric."""


@dataclass(frozen=True, slots=True)
class JudgeItem:
    """One thing for the judge to label.

    Attributes:
        unit: Claim or paragraph.
        unit_id: The claim ID, or ``<rewrite_id>#<paragraph_id>`` for a paragraph.
        source_passage: The whole source passage as ``(paragraph_id, text)``.
        source_paragraph_id: The aligned source paragraph.
        rewritten_markup: The rewritten paragraph with ``<added>`` tags.
        claim: The claim text (claims only).
        in_addition: Whether the claim came from a marked addition.
        generator_model: The model that wrote the rewrite ("" if human).
        synthetic: True when the item comes from synthetic data.
    """

    unit: Unit
    unit_id: str
    source_passage: tuple[tuple[str, str], ...]
    source_paragraph_id: str
    rewritten_markup: str
    claim: str = ""
    in_addition: bool = False
    generator_model: str = ""
    synthetic: bool = False


@dataclass(frozen=True, slots=True)
class JudgeRecord:
    """One judge call and its outcome.

    Attributes:
        unit: Claim or paragraph.
        unit_id: The item's unit ID.
        judge_id: ``judge:<model>:<prompt_version>``, the rater ID in ratings.
        model: Model that answered ("" if the call failed).
        prompt_version: Judge prompt version.
        prompt_sha256: SHA-256 of the prompt file.
        rubric_id: Rubric version.
        rubric_sha256: SHA-256 of the rubric file.
        temperature: Temperature sent, or None.
        timestamp: UTC time of the call.
        synthetic: True for fake-client output or synthetic items.
        labels: Code -> value (empty when invalid).
        rationale: The judge's short explanation.
        errors: Why the output was rejected (empty when valid).
        raw_output: The model's text.
    """

    unit: Unit
    unit_id: str
    judge_id: str
    model: str
    prompt_version: str
    prompt_sha256: str
    rubric_id: str
    rubric_sha256: str
    temperature: float | None
    timestamp: str
    synthetic: bool
    labels: dict[str, str]
    rationale: str
    errors: tuple[str, ...]
    raw_output: str

    @property
    def valid(self) -> bool:
        """Whether the output was accepted."""
        return not self.errors

    def to_record(self) -> dict[str, Any]:
        """Return the JSON-serialisable form.

        Returns:
            A dict with ``record_type`` "judgement".
        """
        record: dict[str, Any] = {"record_type": "judgement"}
        for name in self.__slots__:
            value = getattr(self, name)
            record[name] = value.value if isinstance(value, Unit) else value
        record["errors"] = list(self.errors)
        return record

    def to_rating(self) -> Rating:
        """Convert a valid judgement into a rating with the judge as rater.

        Returns:
            The rating.

        Raises:
            JudgeError: If the judgement is invalid.
        """
        if not self.valid:
            raise JudgeError(f"{self.unit_id}: invalid judgement cannot become a rating")
        return Rating(
            rater_id=self.judge_id,
            unit=self.unit,
            unit_id=self.unit_id,
            labels=dict(self.labels),
            rubric_id=self.rubric_id,
            rubric_sha256=self.rubric_sha256,
            comment=self.rationale,
            synthetic=self.synthetic,
        )


def build_items(rewrites: Sequence[RewriteRecord], claims: Sequence[Claim]) -> list[JudgeItem]:
    """Build judge items: every claim, then every rewritten paragraph.

    Args:
        rewrites: Valid rewrite records.
        claims: Claims decomposed from them.

    Returns:
        Claim items in claim order, then paragraph items in rewrite order.

    Raises:
        KeyError: If a claim's rewrite is not among ``rewrites``.
    """
    by_id = {rewrite.rewrite_id: rewrite for rewrite in rewrites}
    items: list[JudgeItem] = []
    for claim in claims:
        rewrite = by_id[claim.rewrite_id]
        paragraph = next(p for p in rewrite.paragraphs if p.paragraph_id == claim.paragraph_id)
        items.append(
            JudgeItem(
                unit=Unit.CLAIM,
                unit_id=claim.claim_id,
                source_passage=rewrite.source,
                source_paragraph_id=claim.paragraph_id,
                rewritten_markup=paragraph.marked_text(),
                claim=claim.text,
                in_addition=claim.in_addition,
                generator_model=rewrite.model,
                synthetic=rewrite.synthetic or claim.synthetic,
            )
        )
    for rewrite in rewrites:
        for paragraph in rewrite.paragraphs:
            items.append(
                JudgeItem(
                    unit=Unit.PARAGRAPH,
                    unit_id=paragraph_unit_id(rewrite.rewrite_id, paragraph.paragraph_id),
                    source_passage=rewrite.source,
                    source_paragraph_id=paragraph.paragraph_id,
                    rewritten_markup=paragraph.marked_text(),
                    generator_model=rewrite.model,
                    synthetic=rewrite.synthetic,
                )
            )
    return items


def render_codes(codes: Sequence[RubricCode]) -> str:
    """Render rubric codes as the judge's question list.

    Args:
        codes: The codes for one unit.

    Returns:
        One block per code with its question, values and guidance.
    """
    blocks = []
    for code in codes:
        lines = [f"- {code.id}: {code.question}"]
        for value in code.values:
            definition = f": {value.definition}" if value.definition else ""
            lines.append(f"  - {value.id}{definition}")
        if code.yes_when:
            lines.append(f"  Answer yes when: {code.yes_when}")
        if code.no_when:
            lines.append(f"  Answer no when: {code.no_when}")
        blocks.append("\n".join(lines))
    return "\n".join(blocks)


def response_schema(codes: Sequence[RubricCode]) -> str:
    """Render the allowed answers as the JSON schema shown to the judge.

    Args:
        codes: The codes for one unit.

    Returns:
        ``{"labels": {code: [values...]}}`` as JSON.
    """
    return json.dumps({"labels": {code.id: list(code.value_ids) for code in codes}})


def render_item(item: JudgeItem) -> str:
    """Render one item for the judge.

    Args:
        item: The item.

    Returns:
        The item's tagged text.
    """
    passage = "\n".join(f"[{pid}] {text}" for pid, text in item.source_passage)
    aligned = dict(item.source_passage)[item.source_paragraph_id]
    parts = [
        f"<source_passage>\n{passage}\n</source_passage>",
        f'<aligned_source_paragraph id="{item.source_paragraph_id}">\n{aligned}\n'
        "</aligned_source_paragraph>",
        f"<rewritten_paragraph>\n{item.rewritten_markup}\n</rewritten_paragraph>",
    ]
    if item.unit is Unit.CLAIM:
        marked = "true" if item.in_addition else "false"
        parts.append(f'<claim from_marked_addition="{marked}">\n{item.claim}\n</claim>')
    return "\n".join(parts)


def parse_judgement(output: str, rubric: Rubric, unit: Unit) -> tuple[dict[str, str], str]:
    """Parse and validate a judge output.

    Args:
        output: The model's text.
        rubric: The rubric.
        unit: The unit judged.

    Returns:
        ``(labels, rationale)``.

    Raises:
        JudgeError: If the JSON is invalid or the labels do not fit the rubric.
    """
    text = _FENCE.sub("", output.strip())
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise JudgeError("no JSON object in the output")
    try:
        data: Any = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise JudgeError(f"invalid JSON: {exc}") from exc
    labels = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(labels, dict) or not all(isinstance(v, str) for v in labels.values()):
        raise JudgeError("'labels' must be an object of string values")
    problems = rubric.validate_labels(unit, labels)
    if problems:
        raise JudgeError("; ".join(problems))
    rationale = data.get("rationale", "")
    return {str(k): str(v) for k, v in labels.items()}, str(rationale)


def judge_items(
    items: Sequence[JudgeItem],
    rubric: Rubric,
    client: LLMClient,
    *,
    judge_model: str,
    temperature: float | None = None,
    prompt: PromptTemplate | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[JudgeRecord]:
    """Judge every item.

    Args:
        items: Claims and/or paragraphs to judge.
        rubric: The rubric.
        client: The LLM client.
        judge_model: The judge's requested model (recorded; checked against
            each item's generator).
        temperature: Sampling temperature, or None for the default.
        prompt: The judge prompt; ``judge_v1`` when None.
        progress: Optional callback for progress messages.

    Returns:
        One record per item, valid or not.

    Raises:
        JudgeError: If the judge model is the model that wrote an item's rewrite.
    """
    template = prompt or load_prompt("judge_v1")
    report = progress or (lambda _message: None)
    judge_id = f"judge:{judge_model}:{template.version}"
    records: list[JudgeRecord] = []
    for item in items:
        # decisions.md §1.4: never let the generator grade its own output.
        if judge_model != FAKE_MODEL and item.generator_model == judge_model:
            raise JudgeError(f"{item.unit_id}: the judge model wrote this rewrite")
        codes = rubric.codes_for(item.unit)
        system, user = template.render(
            unit_description=UNIT_DESCRIPTIONS[item.unit],
            codes=render_codes(codes),
            response_schema=response_schema(codes),
            item=render_item(item),
        )
        request = LLMRequest.from_prompt(
            user,
            system=system,
            max_tokens=template.max_tokens,
            temperature=temperature,
            prompt_version=template.version,
        )
        records.append(_judge_one(item, request, client, judge_id, template, rubric, temperature))
        report(f"{item.unit_id}: {'ok' if records[-1].valid else 'INVALID'}")
    return records


def _judge_one(
    item: JudgeItem,
    request: LLMRequest,
    client: LLMClient,
    judge_id: str,
    template: PromptTemplate,
    rubric: Rubric,
    temperature: float | None,
) -> JudgeRecord:
    """Send one judge request and record the outcome.

    Args:
        item: The item.
        request: The request.
        client: The LLM client.
        judge_id: The judge's rater ID.
        template: The prompt (for provenance).
        rubric: The rubric.
        temperature: Temperature sent.

    Returns:
        The record; failures carry their error and no labels.
    """
    timestamp = utc_now_iso()
    model, raw, synthetic = "", "", item.synthetic
    labels: dict[str, str] = {}
    rationale = ""
    errors: tuple[str, ...] = ()
    try:
        response = client.complete(request)
        model, raw = response.model, response.text
        synthetic = synthetic or response.synthetic
        labels, rationale = parse_judgement(response.text, rubric, item.unit)
    except (LLMError, JudgeError) as exc:
        errors = (f"{type(exc).__name__}: {exc}",)
    return JudgeRecord(
        unit=item.unit,
        unit_id=item.unit_id,
        judge_id=judge_id,
        model=model,
        prompt_version=template.version,
        prompt_sha256=template.sha256,
        rubric_id=rubric.id,
        rubric_sha256=rubric.sha256,
        temperature=temperature,
        timestamp=timestamp,
        synthetic=synthetic,
        labels=labels,
        rationale=rationale,
        errors=errors,
        raw_output=raw,
    )
