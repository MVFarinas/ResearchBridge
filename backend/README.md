# backend/ — Django backend (Phases 2, 4 and 5)

Corpus storage, the licence gate (decisions.md §1.1) and PMC ingestion, with a Procrastinate
worker on the same codebase (Phase 2), and the reader API for the web app (Phases 4-5). Details,
decisions and results: [docs/phase-notes/phase-2.md](../docs/phase-notes/phase-2.md) and
[docs/phase-notes/phase-4-5.md](../docs/phase-notes/phase-4-5.md).

| Package | What |
|---|---|
| `rb_backend.corpus` | `Paper`, `PaperVersion`, `Section`, `Paragraph`, `Figure`; licence provenance (`LicenceRecord`, `PermissionsBlockRecord`); the `LicenceReview` queue; the gate (`gate.evaluate_version`, `precedence.resolve_licence`); the **gated read API** (`access`, and the `displayable()` / `rewriteable()` querysets); the static bypass check (`accesscheck`). |
| `rb_backend.annotations` | W3C Web Annotation-shaped `Annotation` with provenance, plus `AnnotationRevision`, `Vote`, `Report`. |
| `rb_backend.ingestion` | PMC Cloud Service client (`pmc`), ESearch discovery (`eutils`), the pipeline, worker tasks, and the `ingest_pmc` / `recheck_licences` commands. |
| `rb_backend.metadata` | Cached clients for OpenAlex, NIH iCite, Crossref and the PMC ID converter (`CachedResponse`, "as of" dates, stale fallback), and the paper-level credibility signals. |
| `rb_backend.discovery` | Corpus full-text search (`SearchDocument`, built by the gate), OpenAlex search with availability tags, and the lookup flow (`LookupRequest`, daily budget, worker job status). |
| `rb_backend.api` | Django REST framework endpoints under `/api/v1/`: `papers/<key>/`, `papers/<key>/credibility/`, `search/`, `lookup/`, `lookup/requests/<id>/`. |

**The one rule for later phases:** read papers, versions, sections, paragraphs, figures and
annotations only through `rb_backend.corpus.access` or the `displayable()` / `rewriteable()`
queryset methods. The test suite fails if a module outside the corpus internals does otherwise.

## Run it locally

```sh
make setup                                   # .venv with the locked environment
RB_DB_PORT=5433 make db-up                   # Postgres 16 + pgvector (docker compose)
cd backend
export DJANGO_DEBUG=true                     # or set DJANGO_SECRET_KEY
../.venv/bin/python manage.py migrate
../.venv/bin/python manage.py createsuperuser   # for the admin (licence review queue)

# Discover and queue articles, then let the worker ingest them
../.venv/bin/python manage.py ingest_pmc --limit 50 --query "asthma AND 2024[pdat]"
../.venv/bin/python manage.py procrastinate worker --queues ingestion --one-shot

../.venv/bin/python manage.py corpus_stats              # counts by licence and gate status
../.venv/bin/python manage.py recheck_licences --offline  # recompute decisions, no network
../.venv/bin/python manage.py rebuild_search_index      # only for versions stored before Phase 4
../.venv/bin/python manage.py runserver                 # API at /api/v1/, admin at /admin/
```

`ingest_pmc --sync` ingests inline without the worker. Without `--one-shot` the worker keeps
running and also schedules the daily re-check of stale articles.

## Tests

The backend tests need the local Postgres (`make db-up` first); pytest-django creates and drops a
separate test database. Ingestion tests use recorded responses in `tests/fixtures/pmc` and never
the network. `make check` from the repository root runs lint, mypy and every package's tests.

## Docker image

```sh
docker build -f backend/Dockerfile -t researchbridge-backend .    # from the repository root
docker run --rm -e DATABASE_URL=postgres://... -e DJANGO_SECRET_KEY=... researchbridge-backend django-admin migrate
docker run --rm -p 8000:8000 -e DATABASE_URL=... -e DJANGO_SECRET_KEY=... -e DJANGO_ALLOWED_HOSTS=localhost researchbridge-backend
docker run --rm -e DATABASE_URL=... -e DJANGO_SECRET_KEY=... researchbridge-backend django-admin procrastinate worker
```

Behind a hosting platform's HTTPS proxy (Render, Railway), also set
`DJANGO_TRUST_PROXY_SSL_HEADER=true` and `DJANGO_SECURE_SSL_REDIRECT=true`. Leave the first one
off when the container is reachable directly, as above: any client could then claim HTTPS by
sending `X-Forwarded-Proto`. Every setting is listed in `.env.example`.

## Data acknowledgement

Full text and metadata come from the NIH National Library of Medicine (NLM) PubMed Central Article
Datasets on AWS (<https://registry.opendata.aws/ncbi-pmc/>). Their use does not imply NLM
endorsement.
