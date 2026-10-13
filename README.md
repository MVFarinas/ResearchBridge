# ResearchBridge

Makes openly licensed scientific papers understandable to lay readers: a faithful plain-English
rewrite beside the original, inline explanations, a structured appraisal summary, neutral
paper-level credibility signals and per-paper discussion.

- Spec: [decisions.md](decisions.md) · order of work: [Plan.md](Plan.md)
- Contributing: [docs/conventions.md](docs/conventions.md) · licences: [docs/licence-inventory.md](docs/licence-inventory.md)
- Phase notes: [docs/phase-notes/](docs/phase-notes/)

Quick start (Python 3.12; Docker Desktop or OrbStack for the database):

```sh
make setup && make check     # install the locked environment, then lint, typecheck, test
make db-up                   # local Postgres 16 + pgvector on 127.0.0.1:${RB_DB_PORT:-5433}
```
