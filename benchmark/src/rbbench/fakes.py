"""Deterministic SYNTHETIC responses for the fake LLM client.

Nothing here is model output. Each responder produces text in the format a
step expects, so the parsers and the pipeline can be exercised offline, and
every response names itself as synthetic:

* rewrite: each source paragraph's first sentence, copied verbatim and
  prefixed ``[SYNTHETIC FAKE REWRITE]``, plus one marked addition that says
  it is synthetic. It is not a plain-English rewrite.
* decomposition: the paragraph split into sentences (one "claim" each).
* judge: labels chosen by a hash of the item, mostly the first allowed value
  of each code, with a rationale that says it is synthetic.

The responder dispatches on the request's ``prompt_version`` prefix.
"""

from __future__ import annotations

import hashlib
import json
import re

from rbbench.sentences import sentence_spans, split_sentences
from rbcore.llm import LLMRequest
from rbcore.llm.fake import request_fingerprint

SYNTHETIC_REWRITE_PREFIX = "[SYNTHETIC FAKE REWRITE]"
SYNTHETIC_ADDITION = "[SYNTHETIC FAKE ADDITION, not real context.]"
SYNTHETIC_RATIONALE = "[SYNTHETIC FAKE JUDGE OUTPUT: not a real judgement.]"

_SOURCE = re.compile(r'<source id="([^"]+)">\s*(.*?)\s*</source>', re.DOTALL)
_REWRITTEN = re.compile(r'<rewritten id="([^"]+)">\s*(.*?)\s*</rewritten>', re.DOTALL)
_ADDED = re.compile(r"<added>(.*?)</added>", re.DOTALL)
_SCHEMA = re.compile(r"<response_schema>\s*(.*?)\s*</response_schema>", re.DOTALL)
_ITEM = re.compile(r"<item>\s*(.*?)\s*</item>", re.DOTALL)
# Out of 100 hash buckets, how many synthetic judge labels deviate from the default.
_DEVIATION_PERCENT = 15


def synthetic_responder(request: LLMRequest) -> str:
    """Return a synthetic response in the format the request's step expects.

    Args:
        request: The request; ``prompt_version`` selects the format.

    Returns:
        The synthetic text.
    """
    prompt = request.messages[-1].content
    version = request.prompt_version or ""
    if version.startswith("rewrite_"):
        return fake_rewrite(prompt)
    if version.startswith("decompose_"):
        return fake_decomposition(prompt)
    if version.startswith("judge_"):
        # The judge's response schema lives in the system prompt.
        return fake_judgement(f"{request.system or ''}\n{prompt}")
    return f"[SYNTHETIC FAKE LLM OUTPUT {request_fingerprint(request)[:16]}]"


def fake_rewrite(prompt: str) -> str:
    """Build a synthetic rewrite: first source sentence verbatim plus a marked addition.

    Args:
        prompt: A user prompt containing ``<source id="...">`` blocks.

    Returns:
        One ``<rewrite>`` block per source block.
    """
    blocks = []
    for paragraph_id, text in _SOURCE.findall(prompt):
        sentences = split_sentences(" ".join(text.split()))
        first = sentences[0] if sentences else ""
        blocks.append(
            f'<rewrite id="{paragraph_id}">{SYNTHETIC_REWRITE_PREFIX} {first} '
            f"<added>{SYNTHETIC_ADDITION}</added></rewrite>"
        )
    return "\n".join(blocks)


def fake_decomposition(prompt: str) -> str:
    """Build a synthetic decomposition: one claim per sentence of each paragraph.

    Args:
        prompt: A user prompt containing ``<rewritten id="...">`` blocks with
            ``<added>`` markup.

    Returns:
        The decomposition JSON.
    """
    paragraphs = []
    for paragraph_id, markup in _REWRITTEN.findall(prompt):
        # Locate additions in the tag-free text so sentences can be flagged.
        clean, added = _strip_additions(markup)
        claims = [
            {"text": clean[a:b], "in_addition": any(s <= a < e for s, e in added)}
            for a, b in sentence_spans(clean)
        ]
        paragraphs.append({"paragraph_id": paragraph_id, "claims": claims})
    return json.dumps({"paragraphs": paragraphs}, ensure_ascii=False)


def fake_judgement(prompt: str) -> str:
    """Build a synthetic judgement for the codes listed in the prompt's schema.

    Args:
        prompt: A user prompt containing a ``<response_schema>`` JSON object
            (``{"labels": {code: [values, ...]}}``) and an ``<item>``.

    Returns:
        Judge JSON with one allowed value per code and a synthetic rationale.
    """
    schema_match = _SCHEMA.search(prompt)
    codes: dict[str, list[str]] = (
        json.loads(schema_match.group(1))["labels"] if schema_match else {}
    )
    item_match = _ITEM.search(prompt)
    item = item_match.group(1) if item_match else prompt
    labels = {}
    for code, values in codes.items():
        # Hash bucket per (item, code): stable, and mostly the first value.
        bucket = int(hashlib.sha256(f"{code}\x00{item}".encode()).hexdigest()[:8], 16) % 100
        deviate = bucket < _DEVIATION_PERCENT and len(values) > 1
        labels[code] = values[1 + bucket % (len(values) - 1)] if deviate else values[0]
    return json.dumps({"labels": labels, "rationale": SYNTHETIC_RATIONALE})


def _strip_additions(markup: str) -> tuple[str, list[tuple[int, int]]]:
    """Remove ``<added>`` tags, returning the clean text and the added spans.

    Args:
        markup: Text with ``<added>`` tags.

    Returns:
        ``(clean_text, [(start, end), ...])``.
    """
    clean: list[str] = []
    spans: list[tuple[int, int]] = []
    cursor = 0
    length = 0
    for match in _ADDED.finditer(markup):
        before = markup[cursor : match.start()]
        clean.append(before)
        length += len(before)
        spans.append((length, length + len(match.group(1))))
        clean.append(match.group(1))
        length += len(match.group(1))
        cursor = match.end()
    clean.append(markup[cursor:])
    return "".join(clean), spans
