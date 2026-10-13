# CLAUDE.md

Guidance for Claude (and other agents) working in this repository.

- **Spec:** [decisions.md](decisions.md) (wins over everything). **Order of work:** [Plan.md](Plan.md).
  Prior-art and licence research: [reports/](reports/).
- **Rules:** [docs/conventions.md](docs/conventions.md): Python 3.12 with type hints, a Google
  docstring on every definition (private helpers and tests too), a comment above each logical
  block, real-behaviour tests, no dead code, commit messages with **no trailers**.
- **Licences:** record every new dependency or reused code in
  [docs/licence-inventory.md](docs/licence-inventory.md) before using it. Permissive only; never
  copy copyleft, non-commercial, no-derivatives or unlicensed code.
- **Safety:** never fabricate content or results; LLM calls only via `rbcore.llm.LLMClient`
  (fake in tests, model IDs from config); licence gate via `rbcore.licences`; parse XML only with
  `rbcore.jats` or defusedxml; be polite to public APIs (`rbcore.http.PoliteFetcher`); downloads
  go in the gitignored `data/`.
- **Commands:** `make setup`, `make lint`, `make format`, `make typecheck`, `make test`,
  `make check` (what CI runs), `make lock` (after changing dependencies), `make db-up` / `make db-down`.
  Benchmark (Phase 1): `rbbench --help`; `rbbench dry-run` runs every step offline on the
  fixtures with fake clients and synthetic raters ([benchmark/README.md](benchmark/README.md)).
- **Layout:** `libs/rbcore` (shared library), `tools` (repo checks), `benchmark` (Phase 1),
  `backend` (Phase 2), `scores` (Track R), `web` (Phases 4-5), `docs`, `third_party`.
  A directory with a `pyproject.toml` is a Python package and is picked up automatically.
- **Phase notes:** each phase records what it built, deviations and pending steps in
  `docs/phase-notes/phase-N.md`.
