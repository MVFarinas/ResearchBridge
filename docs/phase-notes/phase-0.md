# Phase 0 — Foundations: notes

Branch `phase-0-foundations`, built 2026-10-13 in an unattended run. Plan.md "Phase 0" plus a
shared core library (`libs/rbcore`) that Phase 1, Phase 2 and Track R build on in parallel.

## What was built

| Area | What | Where |
|---|---|---|
| Layout | `libs/rbcore` (shared library), `tools` (repo checks), placeholders with a README for `benchmark/` (Phase 1), `backend/` (Phase 2), `scores/` (Track R), `web/` (Phases 4-5), plus `docs/` and `third_party/`. | repo root |
| Tooling | Makefile with `setup`, `lock`, `lint`, `format`, `typecheck`, `test`, `check`, `packages`, `db-up`, `db-down`. Python packages are discovered (any `*/pyproject.toml` or `libs/*/pyproject.toml`), so later phases only add their package and run `make lock`. Web targets switch on when `web/package.json` exists. | `Makefile` |
| Lint and types | Root `ruff.toml` (pydocstyle `google`, plus `ANN`, `S`, `T20`, `ERA`, `PT` and more); mypy `strict` per package; `rb-check-docstrings` (docstring on every definition, including private and nested functions and tests) and `rb-check-lock` (every package is in the lock). | `ruff.toml`, `tools/` |
| Dependencies | pip-tools: `requirements/dev.in` (tools) + generated `requirements/packages.in` (one editable line per package) → `requirements/dev.txt` (single lock for the monorepo). | `requirements/` |
| Database | `docker-compose.yml`: `pgvector/pgvector:0.8.7-pg16`, host port `${RB_DB_PORT:-5433}` bound to 127.0.0.1, named volume, `pg_isready` healthcheck. Smoke-tested as project `rb-phase0` on port 5439 (healthy; `CREATE EXTENSION vector` gave 0.8.7 on PostgreSQL 16.15; a vector distance query worked), then brought down with its volume removed. | `docker-compose.yml` |
| CI | GitHub Actions: Python job (`make setup/packages/lint/typecheck/test`), web job gated on `web/package.json` via a detect job (job-level `if` cannot use `hashFiles`). Actions pinned to commit SHAs. | `.github/workflows/ci.yml` |
| Docs | `docs/conventions.md` (coding, docstrings, comments, tests, commits without trailers, data safety, licence and reuse rules); `docs/licence-inventory.md` (seeded from the report's tiers, every dependency added, two pending reviews with evidence); `CLAUDE.md`; root `README.md`. | `docs/`, root |
| `rbcore.jats` | Safe JATS parser (PMC, Europe PMC, PLOS, eLife) → frozen dataclasses: identifiers, title, authors, journal, dates, article type, all abstracts (incl. digests), nested sections and paragraph blocks with stable positional IDs and flattened text (plus each block's source XML), figures and tables (body, back and `floats-group`), every `<permissions>` block attached to the part it covers (article, figure/table, paragraph) or reported as unattached, raw licence fields kept per field with ALI dates and `@specific-use`, COI statements and funding as raw text. Entity references that cannot be resolved fail loudly. | `libs/rbcore/src/rbcore/jats/` |
| `rbcore.licences` | Normaliser for CC URLs (all versions, ports, `legalcode`/`deed` suffixes, `licences` spelling), CC0, public domain, arXiv URIs (non-exclusive and "assumed"), PMC/Europe PMC/bioRxiv/SPDX codes. `derive_permissions` (the §1.1 table + addendum), `decide` (evidence → decision, fail closed, honours ALI `start_date`/`end_date`), `decide_part` (figure-, table- and paragraph-level override; several covering blocks fail closed; blocks on nested objects only narrow). `LicenceField` is the shared provenance vocabulary for every source. | `libs/rbcore/src/rbcore/licences/` |
| `rbcore.config` | `Settings.from_env()`: keys and model IDs from the environment only; secrets hidden from `repr`; judge must differ from generator (§1.4). | `libs/rbcore/src/rbcore/config.py` |
| `rbcore.llm` | `LLMClient` protocol, `FakeLLMClient` (deterministic, output labelled `[SYNTHETIC FAKE LLM OUTPUT …]`, `synthetic=True`), `AnthropicClient` (official SDK, key from `ANTHROPIC_API_KEY`, model from config; **never called** in this run). | `libs/rbcore/src/rbcore/llm/` |
| `rbcore.http` | `PoliteFetcher`: per-host intervals (arXiv 3 s, E-utilities 0.34 s, default 1 s), neutral User-Agent, atomic on-disk cache through unique temporary files (resumable, safe across processes), redirects followed by hand with each hop rate-limited, retries honouring `Retry-After`, size and `Content-Length` checks, http(s) only. | `libs/rbcore/src/rbcore/http.py` |
| Tests | 242 rbcore tests + 11 tools tests. Every §1.1 row (including CC BY-NC-ND and share-alike output licence), fail-closed cases, per-source codes, figure overrides; real fixtures; synthetic snippets (named as such) for structure edge cases; XXE, entity-bomb, DTD and size-limit security tests; config, fake/real LLM client (stubbed SDK), HTTP via `httpx.MockTransport`. | `libs/rbcore/tests/`, `tools/tests/` |
| Fixtures | Five verbatim CC BY 4.0 JATS files with attribution README and SHA-256 manifest (checked by a test): eLife 93719 from PMC **and** from Europe PMC (the latter has prose-only licence), eLife 65180 (Figure 1 has three panel-level blocks: one CC BY-NC, two copyright-only), eLife 61907 (Figure 1 has a prose-only "not covered by CC-BY" block), PLOS Medicine 1004542 (publisher JATS, `license/@xlink:href`). | `libs/rbcore/tests/fixtures/jats/` |

## How to run

```sh
cd <worktree or clone>
make setup                    # .venv with Python 3.12 + locked dev environment
make lint && make typecheck && make test     # or: make check
make db-up                    # Postgres 16 + pgvector on 127.0.0.1:${RB_DB_PORT:-5433}
make db-down
make packages                 # show discovered packages
```

Adding a Python package (Phases 1, 2, R): create `<dir>/pyproject.toml` with
`[tool.pytest.ini_options]` (and `[tool.mypy]` to opt into type checking), code and tests, list its
runtime dependencies in `[project.dependencies]`, then `make lock && make setup` and commit
`requirements/`. To depend on rbcore, add `researchbridge-rbcore` to `dependencies`; the lock
resolves it to the local editable package. Record every new dependency in the licence inventory.

Using the shared library:

```python
from rbcore.jats import parse_jats_file
from rbcore.licences import LicenceEvidence, LicenceField, decide, decide_part

article = parse_jats_file(path)
evidence = [*(article.permissions.evidence() if article.permissions else ())]
evidence.append(LicenceEvidence(LicenceField.PMC_LICENSE_CODE, pmc_json["license_code"]))
decision = decide(evidence)  # one source's evidence, judged today (UTC)
decision.permissions.can_display, decision.permissions.can_rewrite, decision.needs_review
article.unattached_permissions  # non-empty: send the article to licence review
[decide_part(decision, f.permissions) for f in article.figures]
[decide_part(decision, p.permissions) for p in article.iter_paragraphs()]
```

## Deviations and decisions made, with reasons

1. **JATS parsing and licence-permission derivation live in `libs/rbcore`**, not in Phase 1's
   minimal ingester or Phase 2's backend as Plan.md has it. Phase 1 (checking the 12 benchmark
   papers pass §1.1) and Phase 2 both need them and are built in parallel; one shared,
   tested implementation avoids two diverging gates. Phase 2 keeps storage, precedence across
   sources, the review queue and enforcement. (Deviation directed by the build coordinator.)
2. **Extra shared modules: `rbcore.config`, `rbcore.llm`, `rbcore.http`.** Plan.md Phase 0 asks for
   API-key handling with model IDs in config; the LLM interface with a deterministic fake lets
   Phases 1 and 3 run without a key. The polite fetcher gives every phase the same rate limits,
   User-Agent and cache instead of three ad hoc ones.
3. **pubmed_parser (MIT) was evaluated and not used** (licence inventory, "Evaluated and not
   used"): default lxml parser without hardening, bare `except` + `print`, one-level text
   flattening, flat paragraphs without stable IDs or nesting, no licence-field provenance.
   Writing the parser was less work than adapting it to those requirements. No third-party code
   was copied in Phase 0, so `third_party/` holds only its README.
4. **Lock files: pip-tools without hashes, one lock for the whole monorepo.** Hash-checking mode
   (`--require-hashes`) cannot install editable local packages, and the lock installs every
   package editable so they share one environment and one set of versions (no
   "works in benchmark, breaks in backend" drift). Exact `==` pins still make installs
   reproducible. pip-tools is BSD-3 and standard; uv is not available here.
5. **Output licence policy: a rewrite mirrors its source's licence** (CC BY 4.0 → CC BY 4.0,
   CC BY-SA → CC BY-SA, CC0 → CC0, NC variants keep NC). decisions.md only fixes the share-alike
   case; mirroring is always compliant and is the conservative default. **The owner may prefer a
   single policy (for example, release every CC BY / CC0 rewrite under CC BY 4.0); see pending
   items.**
6. **What counts as machine-readable.** `decide` uses `ali:license_ref`, `license/@xlink:href` and
   the per-source code fields only. `license-p` prose is never used (§1.1 addendum, JATS4R), and
   neither is `@license-type` (an uncontrolled vocabulary, usually just "open-access"); both send
   the paper to review. Crossref/OpenAlex fields are recorded as `LicenceField`s but are never the
   gate (§1.1 addendum).
7. **Conflicts fail closed.** If machine-readable values in one source name different licence
   families (for example `ali:license_ref` CC BY and `xlink:href` CC BY-ND, or a CC URI next to an
   unrecognised publisher licence), the decision is "no display, no rewrite, needs review".
   Different versions of the same family agree, because versions do not change the gate.
8. **A figure/table with its own `<permissions>` block but no machine-readable licence fails
   closed** (no display, needs review), even when the copyright holder is the article's authors:
   the block exists because the object is licensed differently, and its prose cannot be trusted
   automatically. Seen in real data (eLife 61907 Figure 1). The same applies to paragraphs
   (`decide_part`, which replaced `decide_figure` in fix round 1).
9. **Definite refusals are not review cases.** `TDM`, arXiv non-exclusive and bioRxiv `cc_no`
   decide "no" with `needs_review=False`; review is for evidence a human could resolve.
10. **Strict XML parsing (no `recover`)**: malformed files raise `JatsParseError`. Recovery can
    silently drop elements such as a figure's permissions block, which would widen the gate.
11. **`AnthropicClient` does not enable server-side model fallbacks** (the Claude API skill's
    default). A fallback silently swaps models, which would corrupt the Phase 1 benchmark's
    attribution of each output to one model. Refusals raise `LLMRefusalError`; the caller decides.
12. **`tools/` package** (`rb_devtools`, not in the requested layout) holds the docstring and lock
    checks so they are linted, typed and tested like any other package.
13. **Compose binds Postgres to 127.0.0.1** rather than all interfaces: the dev credentials are
    public in `.env.example`.

### Added in fix round 1 (after independent review)

14. **Every `<permissions>` block is accounted for.** JATS allows `<permissions>` on `graphic`,
    `media`, `fig-group`, `table-wrap-group`, `disp-quote`, `boxed-text`, `statement`,
    `supplementary-material` and `sec-meta`, not only on `fig`/`table-wrap`. The parser now gives
    each figure, table and paragraph the tuple of every block that applies to it (enclosing ones
    and ones inside it, except inside a nested float), records where each block was attached
    (`PermissionsBlock.context`), and reports any block it cannot attach in
    `Article.unattached_permissions`. `permissions` is never flattened into paragraph text.
    `Figure.permissions` changed from `PermissionsBlock | None` to a tuple (empty = inherits).
15. **Several blocks on one part fail closed.** `decide_part` never chooses between blocks: a
    figure with an open block and a closed block on its graphic gets no display and review. This
    also fixed a real case: eLife 65180 Figure 1 has three panel-level blocks (CC BY-NC, and two
    "not covered by CC-BY" copyright blocks); the original parser read only the first and
    displayed the figure as CC BY-NC.
16. **NISO ALI dates are honoured** (`decide(..., today=...)`, default today in UTC). A licence
    with a past `end_date` or an unparsable date fails closed with review. A reference with a
    future `start_date` (delayed open access) is not in force: if no other dated reference is in
    force today the paper gets no display and review; otherwise it is set aside with a note (see
    19). Among dated references in force the latest `start_date` supersedes earlier ones (the
    ALI embargo-transition pattern); undated values always count.
    A future `end_date` grants but sets review. `ali:free_to_read` dates are recorded for
    reviewers only. Re-run `decide` when an embargo date passes; nothing schedules that yet.
17. **`@specific-use` and `@license-type` raise review, never permissions.** If every
    machine-readable value in force is scoped by a `@specific-use` other than `vor` (for example
    `textmining`) and nothing unscoped agrees, the licence still stands but `needs_review=True`.
    An `@license-type` that normalises to a different recognised family also sets review.
    License-p prose is still never consulted, not even to clear a flag (§1.1 addendum).

### Added in fix round 2 (after independent review)

18. **Blocks on objects nested inside a part never widen it.** Fix round 1 let a single
    `<permissions>` block anywhere inside a paragraph replace the article decision, so a CC BY
    block on an inline `<media>`, `<disp-quote>` or `<supplementary-material>` inside a `<p>` of a
    CC BY-ND article made the paragraph rewritable (fail open). The parser now marks such blocks
    `PermissionsBlock.inner=True`: for a paragraph block, every block that is not its direct child
    (or on an enclosing element); for a figure or table, every block not reached only through its
    `graphic`, `media` or `alternatives` (so caption blocks are inner). `decide_part` decides the
    part from its covering blocks as before, then keeps that decision only if every inner block
    allows at least as much (display, rewrite, and no added non-commercial, attribution, or
    different share-alike condition); otherwise the part fails closed with review, because one
    decision cannot express the mix. An inner block therefore never widens a part.
19. **Both halves of an embargo transition are covered.** Fix round 1 refused a paper as soon as
    any reference had a future `start_date`, even when an earlier dated licence was in force
    (for example CC BY-NC-ND from 2024 and CC BY from 2027, judged in 2026). Now a future-dated
    reference is set aside, with a "re-check then" note, whenever at least one dated reference
    is in force today, so the current licence applies until the transition. When the only
    other values are undated (for example an undated `xlink:href` beside a future-dated
    `ali:license_ref`), the paper is still refused until that date, because the undated value
    may be meant to start on the same date.
18. **Unresolvable entity references fail the parse** (`JatsParseError`) instead of silently
    dropping their text. Entities are never expanded, so `&nbsp;`-style references (internal
    DTD subset, or left for an external DTD) cannot be read safely. None of 60 real PMC, Europe
    PMC and PLOS files tried uses one; all parse.
19. **Objects in `<floats-group>`** are parsed after body and back (stable numbering continues)
    and get the section of the first `xref` that cites them (`section_id=None` if uncited).

## Findings later phases should know

- **Every PMC Cloud Service copy we have seen carries only `ali:license_ref
  specific-use="textmining"`** (60 real files from eLife, Springer Nature, OUP, BMJ, Cureus, Wiley,
  Frontiers and Elsevier journals: no `license/@xlink:href`). `decide` on the JATS alone therefore
  grants but sets `needs_review`. Pass the PMC JSON `license_code` (the §1.1 addendum's first
  precedence, fetched from the same bucket) in the same `decide` call: when it agrees, no review
  is needed; when it disagrees, the paper fails closed.

- **Prefer the PMC Cloud Service copy of an article over Europe PMC's `fullTextXML`.** For the
  same eLife article, PMC's XML has `ali:license_ref`, while Europe PMC's has only `license-p`
  prose (so it fails closed) and moves back matter (bios, competing interests, references) into
  `<body>` sections with `fn-type` removed. Both copies are fixtures.
- **Temperature 0 may not be settable on the Sonnet 5.5 / Opus 5.5 generation.** The bundled
  Claude API reference (cached 2026-10-06) says non-default sampling parameters return HTTP 400 on
  Claude Sonnet 5.5 and are removed on Opus 5.5. Plan.md Phase 1 wants a temperature-0 arm, so the
  Phase 1 design may need adjusting (for example, a model that still accepts temperature, or
  effort levels instead). Not verified against the live API (no key). `LLMRequest.temperature`
  defaults to `None` and is only sent when set.
- **libxml2 2.14 quirk:** `XMLParser(collect_ids=False)` makes lxml try to load the external DTD
  (blocked by `no_network=True`, but it then fails the parse). `rbcore.jats` leaves `collect_ids`
  at its default; anyone building another lxml parser should do the same.
- **libxml2 refuses entity bombs** with "Maximum entity amplification factor exceeded"; XXE
  entities stay unresolved with `resolve_entities=False`.
- **Paragraph IDs are positional per article version.** A new version can renumber; store IDs
  with the version (Plan.md's `PaperVersion`).
- **macOS's `/usr/bin/make` is GNU Make 3.81, which ignores `.SHELLFLAGS`** (found in Track R's
  review, fixed on the Track R branch). So `-e -u -o pipefail` are inactive in every local
  recipe, and before the fix a failing package other than the last did not fail `make test` or
  `make typecheck` locally (CI's Make 4.x was unaffected). The package loops now end with
  `|| exit 1`, which works in any Make. Recipes must not rely on `.SHELLFLAGS` for failure: keep
  each command on its own recipe line, or exit explicitly inside loops and pipelines.

## Pending the owner (manual steps)

1. **Licence review: Hypothesis client.** Evidence is in the inventory (§4): BSD-2-Clause plus an
   MIT-licensed "annotator" subcomponent, both permissive. To close: pick the commit to adapt,
   re-read `LICENSE` at that commit, copy with headers, put the full licence text in
   `third_party/hypothesis-client/LICENSE`, and mark the inventory row `adapted`.
2. **Licence review: PaperCraft** (`allenai/pdf-component-library`). The repository has no LICENSE
   file; npm `@allenai/pdf-components@1.0.2` declares Apache-2.0. Decide whether depending on the
   npm package is acceptable; for copying source, ask allenai to add a LICENSE file (or get
   written confirmation) first. Record the outcome in the inventory.
3. **Decide the rewrite output-licence policy** (deviation 5): keep "mirror the source licence", or
   choose one licence for rewrites of CC BY / CC0 papers. If changed, update
   `derive_permissions` and its tests, and record a decision in decisions.md.
4. **When ready to run real LLM calls:** create an Anthropic API key in the Console, put it in a
   local `.env` (never committed) as `ANTHROPIC_API_KEY`, set `RB_LLM_GENERATION_MODEL` and a
   *different* `RB_LLM_JUDGE_MODEL`, then load it with `set -a; source .env; set +a`. Nothing
   in Phase 0 calls the API.
5. **Optional keys:** `OPENALEX_API_KEY` (free key raises the daily allowance) and `NCBI_API_KEY`
   (raises E-utilities to 10 requests/s). Code works without them.
6. **After the branch is pushed:** confirm GitHub Actions is enabled for the repository and that the
   first CI run passes on Linux (it has only been run locally on macOS); optionally protect `main`
   to require the `Python (lint, typecheck, test)` check.

## Known limitations

- Not parsed: `sub-article` (eLife peer-review material; skipped on purpose), supplementary
  material, `trans-abstract`, table cell text (tables keep caption, footnotes and source XML only),
  references (`ref-list`), and text blocks (for example `boxed-text`) placed in `floats-group`;
  any `<permissions>` on those is reported in `unattached_permissions`.
- Part-level permissions attach to paragraphs, figures and tables; a section `title` or a figure
  caption has no separate decision (it follows its section's paragraphs or its figure).
- No real CC BY article using `<floats-group>` was found: 8 probed PMC copies (Data in Brief,
  Scientific Reports, NAR, BMJ Open, Cureus, Ecology and Evolution, Frontiers in Immunology,
  Heliyon) place floats in the body. The `floats-group` handling is tested on a synthetic snippet
  only.
- MathML without TeX or `@alttext` flattens to its raw token text (for example "x2" for x²).
- Paragraph `text` is plain text; there is no offset map to rendered HTML yet, which W3C
  `TextPositionSelector`s will need (Phase 4).
- COI and funding extraction is heuristic (fn types, section types and titles such as "Competing
  interests" or "Disclosures"); it has not been measured against a labelled corpus.
- The fixture set is five articles from two publishers' pipelines (eLife via PMC/Europe PMC,
  PLOS). Other publishers' JATS variants (BMC, Frontiers, MDPI) are untested.
- `PoliteFetcher` is synchronous and per-process: rate limits are not shared between concurrent
  processes (cache writes are safe across processes), and it does not read robots.txt (it is
  meant for APIs and the PMC bucket). `Content-Length` is checked only for responses without a
  `Content-Encoding`.
- The Docker image is pinned by tag, not digest. The lock was compiled on macOS; all pins are
  platform-independent versions, but CI on Linux has not run yet.
- Distribution names `researchbridge-rbcore` and `researchbridge-devtools` are unregistered on
  PyPI. The `Private :: Do Not Upload` classifier blocks accidental uploads, and the lock installs
  them from local paths, so a same-named public package would not be picked up by `make setup`.
