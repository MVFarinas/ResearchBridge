# rbcore — ResearchBridge shared core library

Python package `rbcore` (distribution `researchbridge-rbcore`). Built in Phase 0 and shared by
Phase 1 (benchmark), Phase 2 (backend) and Track R (scores), which are built in parallel.

| Module | What it does |
|---|---|
| `rbcore.jats` | Safe JATS XML parsing (PMC, Europe PMC, PLOS, eLife) into immutable dataclasses: identifiers, metadata, abstracts, nested sections and paragraphs with **stable positional IDs**, figures, tables and paragraphs with every `<permissions>` block that applies to them (plus any block that fits nowhere, reported as unattached), raw licence fields with ALI dates and `@specific-use`, COI statements and funding. |
| `rbcore.licences` | Normalises licence URIs and codes (CC in every version and port, CC0, PMC `license_code`, Europe PMC, bioRxiv, arXiv, SPDX) and applies the decisions.md §1.1 gate: `can_display`, `can_rewrite`, `output_licence`, `non_commercial`. Fails closed, including on ALI embargo dates. Figure-, table- and paragraph-level overrides. |
| `rbcore.config` | `Settings.from_env()`: model IDs and optional keys from the environment. |
| `rbcore.llm` | `LLMClient` protocol, deterministic `FakeLLMClient`, and `AnthropicClient` (official SDK, never called without a key). |
| `rbcore.http` | `PoliteFetcher`: per-host rate limits, neutral User-Agent, atomic on-disk cache, per-hop rate-limited redirects, retries, size and length checks. |

## Quick use

```python
from rbcore.jats import parse_jats_file
from rbcore.licences import LicenceEvidence, LicenceField, decide, decide_part

article = parse_jats_file("PMC10718527.1.xml")
evidence = list(article.permissions.evidence()) if article.permissions else []
# PMC copies carry only text-mining-scoped ali:license_refs; pass the PMC JSON
# license_code in the same call so an unscoped value can confirm them.
evidence.append(LicenceEvidence(LicenceField.PMC_LICENSE_CODE, "CC BY"))
decision = decide(evidence)
if article.unattached_permissions:
    ...  # part of the article is licensed differently: send to licence review
for paragraph in article.iter_paragraphs():
    if decide_part(decision, paragraph.permissions).permissions.can_rewrite:
        print(paragraph.id, paragraph.text)  # e.g. "sec2.1-p3", "..."
for figure in article.figures:
    print(figure.id, decide_part(decision, figure.permissions).permissions)
```

## Paragraph ID scheme

`body-p1` (paragraphs before the first section), `sec2`, `sec2.1`, `sec2.1-p3`; abstracts
`abs1`, `abs1.sec1-p1`; back matter `back.sec1-p1`; figures `fig1`, tables `table1`. IDs
depend only on structural position, so re-parsing the same article version gives the same IDs.
A new article *version* may renumber; store IDs per version.

## Licence gate in one paragraph

`decide()` only uses machine-readable fields (`ali:license_ref`, `license/@xlink:href`, and the
per-source codes), never `license-p` prose or `@license-type`, and never aggregator fields
(Crossref, OpenAlex). Missing, prose-only, conflicting or unrecognised evidence gives
`can_display=False, can_rewrite=False`, with `needs_review=True` where a human could resolve it.
NISO ALI dates are honoured: a licence whose `start_date` is in the future (an embargo) or whose
`end_date` has passed is not in force. A decision can grant permissions and still set
`needs_review` (use-scoped `@specific-use` evidence with nothing unscoped agreeing, a
contradicting `@license-type`, a future `end_date`). A part (figure, table, paragraph) with
several covering permissions blocks fails closed; a block on an object nested inside it (an
inline media item, quotation or supplementary file, or anything in a figure caption) can only
narrow the part, never widen it. Precedence *across* sources (PMC JSON vs Europe PMC vs JATS vs arXiv vs bioRxiv) is Phase 2's job.

Tests: `make test` (or `cd libs/rbcore && ../../.venv/bin/pytest`). Fixture attribution:
[tests/fixtures/jats/README.md](tests/fixtures/jats/README.md).
