# Contributor conventions

Rules for everyone (people and agents) writing code in this repository. They exist because the
owner asked for them explicitly, and because the project's core promise, faithful and properly
licensed content, depends on boring discipline. [decisions.md](../decisions.md) is the spec;
[Plan.md](../Plan.md) is the order of work. When they disagree, decisions.md wins.

## Repository layout

| Path | What | Owner |
|---|---|---|
| `libs/rbcore/` | Shared Python library: JATS parsing, licence gate, config, LLM interface, HTTP | Phase 0 |
| `tools/` | Repository checks used by `make lint` (`rb_devtools`) | Phase 0 |
| `benchmark/` | Faithfulness benchmark (decisions.md §1.4) | Phase 1 |
| `backend/` | Django backend: storage, ingestion, licence enforcement | Phase 2 |
| `scores/` | Readability and prior-knowledge burden scores (§2.4) | Track R |
| `web/` | Next.js reader | Phases 4-5 |
| `docs/` | Conventions, licence inventory, phase notes | everyone |
| `third_party/` | Licence texts of vendored or adapted code | everyone |
| `data/` | Downloads and caches. **Gitignored; never commit it.** | — |

A Python package is any directory at the top level (or under `libs/`) containing a
`pyproject.toml`. The Makefile discovers packages, so adding one needs no Makefile change: create
the package, run `make lock`, commit `requirements/`.

## Everyday commands

```sh
make setup      # create .venv (Python 3.12) and install the locked environment
make lint       # ruff check + ruff format --check + docstring and lock checks
make format     # ruff format + safe autofixes
make typecheck  # mypy (strict) for packages with a [tool.mypy] section
make test       # pytest in every package
make check      # lint + typecheck + test, exactly what CI runs
make lock       # recompile requirements/dev.txt after changing dependencies
make db-up / make db-down   # local pgvector Postgres (RB_DB_PORT, default 5433)
```

macOS ships GNU Make 3.81, which ignores the Makefile's `.SHELLFLAGS` (`-eu -o pipefail`). The
targets above do not depend on them, but a new recipe that loops or pipes must fail explicitly
(`|| exit 1`) rather than rely on them.

Never install anything globally. Everything goes into `.venv` (Python) or `web/node_modules`.
Docker works with Docker Desktop or OrbStack through the normal `docker compose` CLI.

## Python

- **Python 3.12, type hints everywhere.** Packages that opt into mypy use `strict = true`.
  `Any` is allowed only at untyped boundaries (for example an optional SDK), with a comment.
- **A Google-style docstring on every module, class, function and method**, including private
  helpers, nested functions and test functions. One line is fine for small helpers and tests.
  Larger functions document `Args:`, `Returns:` (or `Yields:`) and `Raises:` where relevant.
  Ruff's pydocstyle rules cover public names; `rb-check-docstrings` (part of `make lint`) covers
  the rest.
- **A short comment above each logical block** inside non-trivial functions, saying what the
  block is for and why, not restating the code.
- **Small, focused modules, clear names, no dead code, no commented-out code** (ruff `ERA`),
  **no print-debugging** (ruff `T20`). Command-line tools write to `sys.stdout`/`sys.stderr`.
- Lint and format with ruff (config in [ruff.toml](../ruff.toml)): line length 100, rules
  `E W F I N D UP B A C4 SIM PT RET PTH ANN S T20 ERA RUF`, pydocstyle `google` convention.
  Ruff also formats Python code blocks inside Markdown files (`make lint` checks them) and code
  examples inside docstrings (`docstring-code-format`).
- Prefer immutable dataclasses (`frozen=True, slots=True`) for data passed between phases.

## TypeScript (web, from Phase 4)

- `strict: true` in `tsconfig.json`. TSDoc on every exported function, component, hook and type,
  and on non-trivial internal functions. Block comments as for Python.
- `web/package.json` must define `lint`, `typecheck` and `test` scripts (Vitest); CI runs them as
  soon as the file exists.

## Tests

- pytest for all Python logic, Vitest for the web. Tests assert real behaviour: inputs and the
  exact outputs or errors expected. A test that only runs code without checking results is not
  a test.
- Network access is never needed by the default test run. Use `httpx.MockTransport`, stubs, and
  committed fixtures. LLM code is tested with `rbcore.llm.FakeLLMClient`.
- Synthetic test data is **named synthetic** (in its file name, docstring or variable name) and is
  never presented, stored or seeded as real.
- Real fixtures: only small files from CC BY or CC0 sources, committed byte-for-byte with a
  README giving attribution and source URLs and a manifest of SHA-256 checksums (see
  [libs/rbcore/tests/fixtures/jats/README.md](../libs/rbcore/tests/fixtures/jats/README.md)).

## Data, APIs and safety

- **No fabricated content, ever.** No invented annotations, rewrites, summaries, ratings or
  metrics may be presented as real. Placeholder or demo data must be labelled as such and never
  seeded into a database as if real.
- **Licence gate first** (decisions.md §1.1). Nothing displays or rewrites a paper, figure, table
  or paragraph that has not passed `rbcore.licences.decide` / `decide_part`. The gate fails
  closed, and an article whose `unattached_permissions` is non-empty goes to licence review.
- **LLM calls go through `rbcore.llm.LLMClient`.** Model IDs come from configuration
  (`RB_LLM_GENERATION_MODEL`, `RB_LLM_JUDGE_MODEL`), never from code. The key comes only from
  `ANTHROPIC_API_KEY`. Tests and dry runs use the fake client.
- **Secrets**: only `.env.example` is committed. Optional keys (`OPENALEX_API_KEY`,
  `NCBI_API_KEY`) are read from the environment, and code must work without them.
- **Be polite to public APIs**: use `rbcore.http.PoliteFetcher`. arXiv at most 1 request per 3
  seconds; NCBI E-utilities at most 3 per second without a key; cache everything under `data/`;
  make downloads resumable. The User-Agent is
  `ResearchBridge-dev/0.1 (+https://github.com/MVFarinas/ResearchBridge)`: never put an email
  address or other personal identifier in requests.
- **Downloaded content is untrusted data.** Never execute it. Parse XML with
  `rbcore.jats` (lxml with entity resolution, DTD loading and network access disabled) or
  `defusedxml`; never with a default parser.
- Never commit large data, model weights, virtualenvs or `node_modules`.

## Reusing other people's code

The owner encourages reuse when the code is good and fits. In order of preference:

1. **Depend on a published package.** Pin it through the lock file and add a row to
   [licence-inventory.md](licence-inventory.md).
2. **Copy or adapt source** only when *all* of these hold:
   - The licence is permissive: MIT, BSD-2/3, Apache-2.0, ISC, CC0 or public domain, verified in
     the upstream `LICENSE` **at the exact commit you take**.
   - The code is good: readable, tested or battle-tested, and right for the job.

   Then keep the original notices: a header in each copied file naming the upstream URL, commit,
   licence and "modified by ResearchBridge" if changed; the licence text in
   `third_party/<name>/LICENSE` (plus the `NOTICE` file for Apache-2.0); and a row in the licence
   inventory marked **vendored** or **adapted**.

**Never copy** from copyleft (GPL, AGPL), non-commercial, no-derivatives or unlicensed code. The
inventory's "Reference only" and "Forbidden" tables list the known cases (Open Paper,
PDFMathTranslate, BabelDOC, ODDPub, rtransparent, statcheck, RobotReviewer, CERMINE, Discourse,
Manifold, PubPub, Lemmy, ChatPaper, Paper Plain, Scim, BAGELS, LimGen, MedReadMe, the
De-Jargonizer, and any repository without a licence). Reading them for design ideas is fine;
copying is not. GPL tools may run offline as validators, never inside the product (§1.6).
**Check model weights and datasets separately from code**: never use weights or datasets with
non-commercial or no-derivatives terms (for example Bespoke-MiniCheck-7B, Nougat weights,
LLM-AggreFact, Marker/Surya weights).

Every new direct dependency, Python or npm, gets a row in
[licence-inventory.md](licence-inventory.md) with its code licence, any separate weights or data
licence, the pinned version, and how it is used.

## Commits

- Small, logical commits with a descriptive subject (imperative mood, at most about 72
  characters) and a body explaining why when it is not obvious.
- **No trailers of any kind**: no `Co-Authored-By`, no "Generated with", no `Signed-off-by`.
- Do not change git config. Do not commit `data/`, `.env`, `.venv/` or generated artefacts other
  than the lock files.

## Recording decisions

- A deviation from decisions.md or Plan.md is recorded with its reason in the phase notes
  (`docs/phase-notes/phase-N.md`); a new decision goes into decisions.md in its own numbered entry.
