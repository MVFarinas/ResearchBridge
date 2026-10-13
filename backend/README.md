# backend/ — Django backend (Phase 2)

**Owner: Phase 2.** Placeholder created in Phase 0; the Django project does not exist yet.

Purpose: Django + Postgres/pgvector backend with a background worker: the paper and annotation
schema, ingestion (PMC Cloud Service, PLOS), licence storage per version and per figure, precedence
across licence sources, the manual review queue and enforcement of the licence gate. See
[Plan.md](../Plan.md) "Phase 2".

JATS parsing and licence-permission derivation live in `libs/rbcore` (Phase 0 deviation, see
[docs/phase-notes/phase-0.md](../docs/phase-notes/phase-0.md)); this package stores and enforces
their results. Local database: `make db-up` (port from `RB_DB_PORT`, default 5433).
