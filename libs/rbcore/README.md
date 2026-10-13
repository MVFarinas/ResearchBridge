# rbcore — ResearchBridge shared core library

Python package `rbcore` (distribution `researchbridge-rbcore`). Built in Phase 0 and shared by
Phase 1 (benchmark), Phase 2 (backend) and Track R (scores), which are built in parallel.

| Module | What it does |
|---|---|
| `rbcore.jats` | Safe JATS XML parsing (PMC, Europe PMC, PLOS, eLife) into immutable dataclasses: identifiers, metadata, abstracts, nested sections and paragraphs with **stable positional IDs**, figures and tables with their own `<permissions>`, raw licence fields, COI statements and funding. |
| `rbcore.licences` | Normalises licence URIs and codes (CC in every version and port, CC0, PMC `license_code`, Europe PMC, bioRxiv, arXiv, SPDX) and applies the decisions.md §1.1 gate: `can_display`, `can_rewrite`, `output_licence`, `non_commercial`. Fails closed. Figure-level overrides. |
| `rbcore.config` | `Settings.from_env()`: model IDs and optional keys from the environment. |
| `rbcore.llm` | `LLMClient` protocol, deterministic `FakeLLMClient`, and `AnthropicClient` (official SDK, never called without a key). |
| `rbcore.http` | `PoliteFetcher`: per-host rate limits, neutral User-Agent, atomic on-disk cache, retries, size limits. |

## Quick use

```python
from rbcore.jats import parse_jats_file
from rbcore.licences import decide, decide_figure

article = parse_jats_file("PMC10718527.1.xml")
decision = decide(article.permissions.evidence() if article.permissions else [])
if decision.permissions.can_rewrite:
    for paragraph in article.iter_paragraphs():
        print(paragraph.id, paragraph.text)  # e.g. "sec2.1-p3", "..."
for figure in article.figures:
    print(figure.id, decide_figure(decision, figure.permissions).permissions)
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
Precedence *across* sources (PMC JSON vs Europe PMC vs JATS vs arXiv vs bioRxiv) is Phase 2's job.

Tests: `make test` (or `cd libs/rbcore && ../../.venv/bin/pytest`). Fixture attribution:
[tests/fixtures/jats/README.md](tests/fixtures/jats/README.md).
