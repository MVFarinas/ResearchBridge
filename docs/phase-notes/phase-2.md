# Phase 2 — Corpus and licence gate: notes

Branch `phase-2-corpus-licence-gate` (from `phase-0-foundations`), built 2026-10-13 in an
unattended run. Plan.md "Phase 2"; decisions.md §1.1 (with its addendum) and §1.6.

## What was built

| Area | What | Where |
|---|---|---|
| Django project | Django 5.2 LTS (5.2.18), settings from the environment only (`DATABASE_URL` for managed platforms, otherwise the `RB_DB_*` variables the compose file uses; `DJANGO_SECRET_KEY` required unless `DJANGO_DEBUG=true`). Parsing rules are unit-tested in `envconfig`. | `backend/src/rb_backend/settings.py`, `envconfig.py` |
| Postgres + pgvector | `corpus/migrations/0001_enable_pgvector.py` runs `CREATE EXTENSION vector` (Django's `VectorExtension` operation equivalent, no extra dependency). No vector columns yet; they arrive with search/embeddings. | `backend/src/rb_backend/corpus/migrations/` |
| Worker | Procrastinate 3.10 (MIT) via `procrastinate.contrib.django`: Postgres is the queue, so there is no broker to host. Tasks `rb.ingest_pmc_article` (one article, PMC ID as queueing lock, 3 attempts) and the daily periodic `rb.recheck_stale_pmc`. Run with `manage.py procrastinate worker`. | `backend/src/rb_backend/ingestion/tasks.py` |
| Schema: papers | `Paper` (DOI, PMCID, PMID, arXiv ID; `is_retracted`, `retraction_source`, `retraction_date`, `retraction_recorded_at`; check constraints: an identifier is required, a retraction needs a source). `PaperVersion` (source, source version ID, `is_current` with a unique partial index, metadata, journal, dates, article type, source flags, content URLs, MD5/SHA-256, retrieval and last-checked times, parser version, content state). `Section` and `Paragraph` keyed by rbcore's stable IDs (the alignment unit), `Figure` for figures and tables. | `corpus/models/papers.py` |
| Schema: licence provenance | `LicenceRecord`: one row per licence value, with the raw value, the **source field** (`LicenceField`: `pmc_license_code`, `jats_ali_license_ref`, `jats_license_xlink_href`, `jats_license_p`, ...), its normalised family/version/jurisdiction, `@specific-use`, ALI start/end dates, source URL, `retrieved_at`, `last_confirmed_at` and `superseded_at` (history is kept, never overwritten). `PermissionsBlockRecord`: every JATS `<permissions>` block (article, figure/table, paragraph, or unattached), with copyright statement, years, holders and free-to-read dates. | `corpus/models/licensing.py` |
| Schema: derived permissions | `GatedPermissions` (abstract, on `PaperVersion`, `Figure`, `Paragraph`): `gate_status` (pending, approved, review, rejected), `can_display`, `can_rewrite`, `non_commercial`, `attribution_required`, `share_alike`, the licence, the **output licence** (share-alike sets it), decision source, reasons and time. Database check constraints refuse rows that break the §1.1 table (e.g. `can_rewrite` without `can_display`, display while not approved, rewriting an ND licence). | `corpus/models/gated.py` |
| Gate | `gate.evaluate_version` is the only writer of decisions: rebuilds evidence from the stored records, resolves precedence, adds review triggers (unattached permissions blocks, failed parse, a version the source no longer lists), settles against the review queue, removes the stored text of a rejected version (`corpus/retention.py`), then decides every figure, table and paragraph with `rbcore.licences.decide_part`. Re-run on every ingestion, re-check and review resolution, in the same transaction as the evidence it reads. | `corpus/gate.py`, `corpus/blocks.py` |
| Precedence | PMC `license_code` → Europe PMC `license` → JATS (`ali:license_ref`, `license/@xlink:href`) → arXiv OAI-PMH → bioRxiv API. Crossref/OpenAlex are recorded as secondary signals only. See "Precedence rules" below. | `corpus/precedence.py` |
| Review queue | `LicenceReview` (scope version/figure/paragraph, reasons, evidence snapshot and fingerprint, proposed licence, resolution, reviewer, note). Never auto-approved. Resolving one in the admin re-runs the gate; a resolution applies only to the exact evidence it was made for, so changed evidence reopens review. | `corpus/models/licensing.py`, `corpus/reviews.py`, `corpus/admin.py` |
| Enforcement | `displayable()` / `rewriteable()` on the querysets of `Paper`, `PaperVersion`, `Section`, `Paragraph`, `Figure` and `Annotation`, built from one set of `Q` conditions; a part is never more open than its version. `rb_backend.corpus.access` wraps them as the read API for later phases. `accesscheck` is an AST check, run by the test suite over all of `rb_backend`, that fails on any read of a gated model outside the trusted internals that bypasses those methods (managers, related managers, `_default_manager`, `.raw()`, `connection.cursor()`). | `corpus/querysets.py`, `corpus/access.py`, `corpus/accesscheck.py` |
| Annotations | `Annotation` in W3C Web Annotation shape: `target` JSON (source + `TextQuoteSelector` + `TextPositionSelector`, validated against the paragraph's stored text), `body` (`TextualBody`, plain text or Markdown, HTML refused), `motivation`, `provenance` (`llm`, `human`, `llm_edited`), `model`, `prompt_version`, author, verification, supersession, timestamps; scoped to a paper version and paragraph. `AnnotationRevision` (full history, written on every change), `Vote`, `Report` (present, unused until Phase 7). `annotations/w3c.py` validates the W3C target and body shapes; a JSON-LD export is not written yet (no read path needs one before Phase 4). | `annotations/models.py`, `annotations/w3c.py` |
| Ingestion | PMC Cloud Service over plain HTTPS (no AWS SDK, no credentials): bucket listing (parsed with defusedxml) → per-version JSON → JATS XML (MD5-checked against the bucket's `md5`), parsed by `rbcore.jats`. Discovery by NCBI ESearch with the bucket README's filters. All requests through `rbcore.http.PoliteFetcher` (rate-limited, neutral User-Agent, cache in `data/`). Idempotent; re-runs update stale rows. Network requests come first; the version, licence records, content and gate decision are then written in one transaction. An article the bucket stops listing is marked withdrawn and held for review. | `ingestion/pmc.py`, `eutils.py`, `pipeline.py`, `store.py`, `runtime.py` |
| Commands | `ingest_pmc` (`--limit`, `--query`, `--licence any/cc-by/cc0/rewrite/commercial`, `--pmcid`, `--skip-existing`, `--sync`), `recheck_licences` (network re-check through the worker, or `--offline` recompute from stored records; `--older-than-days`, `--pmcid`, `--limit`, `--sync`), `corpus_stats` (JSON counts). | `*/management/commands/` |
| Admin | Papers (versions inline), versions (gate fields, content state, last check, withdrawal), licence records, permissions blocks, figures, paragraphs, the licence review queue (filter by status/scope; resolve with a licence or reject; the gate re-runs on save), annotations (revisions inline), votes and reports. Everything is read-only ("read-mostly") except resolving an open licence review. Sections have no admin page, and report moderation waits for Phase 7. | `corpus/admin.py`, `annotations/admin.py` |
| Docker image | `backend/Dockerfile`: `python:3.12-slim-bookworm`, installs the pinned `requirements/backend.txt` (compiled by `make lock`; a test checks every pin equals `requirements/dev.txt`), then rbcore and the backend without re-resolving, `pip check`, `collectstatic` (WhiteNoise), unprivileged user, gunicorn. The same image runs `django-admin migrate` and `django-admin procrastinate worker`. CI builds it (`backend-image` job). | `backend/Dockerfile` |
| CI | The Python job gets a `pgvector/pgvector:0.8.7-pg16` service on port 5433 for the backend tests. | `.github/workflows/ci.yml` |
| Tests | 145 backend test functions (more cases with parametrisation) on Postgres via pytest-django: every precedence rule, the gate and review settling, the enforcement matrix, figure-level overrides, the access check, ingestion against recorded responses (never the network) including withdrawal, rejection and a simulated crash, tasks and commands, admin pages and the review flow, W3C validation, settings parsing, fixture checksums, the image lock. | `backend/tests/` |

## How to run

```sh
cd <worktree>
make setup                                    # .venv with the locked environment
make db-up COMPOSE_PROJECT=rb-phase2          # Postgres 16 + pgvector on 127.0.0.1:${RB_DB_PORT:-5433}
cd backend
export DJANGO_DEBUG=true                      # or set DJANGO_SECRET_KEY
../.venv/bin/python manage.py migrate         # also creates the Procrastinate tables
../.venv/bin/python manage.py createsuperuser # for the admin and the review queue

# Discover and queue, then run the worker until the queue is empty
../.venv/bin/python manage.py ingest_pmc --limit 100 --query "hypertension AND 2024[pdat]" --licence cc-by
../.venv/bin/python manage.py procrastinate worker --queues ingestion --one-shot

../.venv/bin/python manage.py corpus_stats
../.venv/bin/python manage.py recheck_licences --offline     # recompute, no network
../.venv/bin/python manage.py recheck_licences --older-than-days 7
../.venv/bin/python manage.py runserver      # admin at http://127.0.0.1:8000/admin/

cd .. && make check                          # lint, mypy, all tests (needs the database up)
make db-down COMPOSE_PROJECT=rb-phase2
```

Without `--one-shot` the worker keeps running and schedules the daily re-check of articles not
checked for `RB_RECHECK_MAX_AGE_DAYS` days (default 7), at most `RB_RECHECK_BATCH_SIZE` (500)
per day. `ingest_pmc --sync` ingests inline without the worker. `NCBI_API_KEY` is optional.

## Precedence rules (what the gate does when sources disagree)

1. Evidence is ordered by source precedence. Only machine-readable, non-secondary fields can
   decide; `<license-p>` prose and `@license-type` only ever trigger review (§1.1 addendum).
2. **The top source's definite refusal ends it.** If the highest-precedence source with
   machine-readable evidence says `TDM`, arXiv non-exclusive or all rights reserved, the version
   is rejected without review, and lower sources are not consulted. In PMC, that is the
   `license_code` from the JSON, so author manuscripts are rejected before the XML is fetched.
3. **Otherwise every source must agree.** All evidence is judged together by
   `rbcore.licences.decide`: agreeing sources grant (the recorded source is the highest one);
   different licence families anywhere fail closed into review. This is stricter than "take the
   highest-precedence one" from the task text: taking the top source silently would let a PMC
   code of CC BY override a JATS block that says CC BY-ND. A human resolves real conflicts.
   An agreeing, unscoped PMC code clears the review flag that PMC's JATS
   `specific-use="textmining"` references raise on their own (common in PMC XML).
4. A version licence from a lower agreeing source is borrowed when the top one has none (PMC
   codes are "CC BY" without a version, the JATS says `by/4.0`), so attribution can name the
   exact licence. It never changes a permission.
5. Figures, tables and paragraphs with their own `<permissions>` are decided by
   `rbcore.licences.decide_part` against the version's effective decision: they can only narrow
   it, several blocks or prose-only blocks fail closed into a part-level review, and a part
   without blocks inherits.

## Decisions, deviations and reasons

1. **Worker: Procrastinate (MIT).** Postgres is already required, so a Postgres-backed queue adds
   no service (§1.6 "fewest moving parts", one managed platform). It locks jobs with
   `SELECT ... FOR UPDATE SKIP LOCKED`, wakes workers with LISTEN/NOTIFY, has retries, queueing
   locks (no duplicate jobs per article), periodic tasks and a Django integration, and is
   maintained with a test suite. Rejected (licence inventory, "Evaluated and not used"): Celery
   (needs Redis or RabbitMQ), django-q2 (ORM polling broker), django-tasks (database backend
   pre-1.0; revisit with Django 6).
2. **psycopg is LGPL-3.0.** Django's ORM and Procrastinate both require it; there is no
   permissive PostgreSQL driver Django supports. It is used unmodified as an imported library,
   which places no obligation on our code; its source is never copied. Recorded as an exception
   in the licence inventory.
3. **No third-party code was copied or adapted.** Everything reusable is a dependency (Django,
   Procrastinate, defusedxml, gunicorn, WhiteNoise, pytest-django, django-stubs). Considered:
   pgvector-python's `VectorExtension` (MIT) is a one-line operation, so the migration runs the
   SQL directly; dj-database-url (BSD-3) was not worth a dependency for one URL format;
   ResearchHub's vote/reputation code (MIT) is for Phase 7, when those tables are used.
4. **PLOS comes through PMC, not allofplos.** PLOS deposits every article in PMC, so PLOS papers
   arrive through the same bucket, under the same `license_code` gate and the same pipeline; a
   PLOS fixture (PLOS Medicine e1004542, CC BY 4.0) is ingested in the tests through that route,
   and `ingest_pmc --query '"PLoS Med"[ta]'` selects PLOS journals. allofplos (MIT) would be a
   second pipeline over a 7 GB zip for content we already get. PLOS coverage in the bucket was
   not measured; if PLOS ever lags in PMC, allofplos is the fallback.
5. **Only the current version is ever served.** `displayable()` requires `is_current`; the
   current version is the highest version prefix in the bucket. Older versions keep their
   records for provenance. This is how the "maintain the most current version" term is met;
   the daily re-check keeps it current.
6. **Retraction: shown with a notice, never rewritten** (decided in fix round 2). `is_retracted`
   comes from the current version's JSON (PMC gives no date, so `retraction_date` stays empty and
   `retraction_recorded_at` is when we learnt of it). A retracted paper stays **displayable** and
   is **never rewriteable**: no plain-English version, no rewrite-derived annotations
   (`rewriteable()` excludes it at every level). Why not hide it: decisions.md has no rule on
   retractions; the PMC bucket terms ask redistributors to keep data current, which we meet by
   re-reading the flag on every re-check; and the research notes behind the prior-art report
   (`ingestion_licence_pipeline.md`) give "unpublishing or flagging" as the two options. Flagging
   serves lay readers better: someone who meets a retracted paper elsewhere can find out here that
   it was retracted, which hiding it would prevent. The read API makes the notice part of the
   contract: `access.retraction_notice(paper)` returns the source, date and record time, and every
   reader path that shows a displayable paper must show that notice prominently (stated in
   `corpus/access.py` and `corpus/querysets.py`; Phase 4 builds the banner). A flag PMC later
   withdraws is cleared only if PMC set it. Phase 5 adds Crossref/Retraction Watch as further
   sources. To hide retracted papers instead, add `paper__is_retracted=False` to
   `version_displayable_q()` (`corpus/querysets.py`) and the matching rule in the enforcement tests.
7. **TDM author manuscripts are rejected without downloading the XML**, and any previously stored
   text of a version that turns TDM is purged (records of why stay). More generally, **a rejected
   version keeps no text** (fix round 1): whenever the gate rejects a version (an
   all-rights-reserved JATS licence, a reviewer's rejection), its sections, paragraphs and figures
   are deleted in the same transaction, and its XML is deleted from the download cache in `data/`
   (fix round 2). The article-level permissions blocks that justify the rejection stay active, so
   re-evaluation reaches the same decision, and licence reviews of the deleted parts stay as the
   audit trail (fix round 2); the version's content state becomes `removed`, and its XML is
   fetched again only if new evidence or a reviewer's approval stops the gate rejecting it. ESearch
   discovery
   deliberately includes `author_manuscript[Filter]` with `--licence any`, so the gate's refusal
   is exercised on real data; use `--licence cc-by` (or `rewrite`, `commercial`) to avoid them.
8. **A licence that permits display still waits for parsed full text** (`pending`) before any
   approval, and a version whose XML cannot be parsed goes to review (a failed parse could hide
   part-level restrictions).
9. **Review resolutions are tied to an evidence fingerprint.** A resolution applies only while the
   evidence and reasons it was made for are unchanged; a new licence value reopens review.
10. **Enforcement has three layers:** the queryset methods (the one place the rules live), DB check
    constraints (a raw `UPDATE` that sets `can_rewrite` on an ND licence or display on a rejected
    row fails), and the static access check (new modules in later phases are covered
    automatically). The static check is a guard against mistakes, not a sandbox.
11. **Parts are decided per paragraph as well as per figure/table**, because rbcore attaches
    `<permissions>` to paragraphs too (Phase 0, fix round 1). Section titles follow their version.
12. **The bucket is read over HTTPS without the AWS SDK**: listings are ListObjectsV2 XML parsed
    with defusedxml; JSON and XML are plain GETs. Metadata and listings are never cached, so
    re-runs see changes; XML is cached keyed by its URL, which carries the object's MD5, and the
    MD5 is verified after download. The bucket is polled at most every 0.5 s, and one article is
    ingested at a time per process.
13. **Ruff `RUF012` is off for model modules** (Django `Meta` options are mutable class attributes
    by design); migrations are excluded from docstring rules as generated code.
14. **Withdrawn articles go to review, not straight to deletion** (fix round 1). When the bucket
    lists no version of a stored article, the current version records `source_withdrawn_at` (the
    first time only, so the review evidence is stable) and `last_checked_at`, and the gate sends it
    to licence review with no permissions. A human decides whether to keep it (for example an
    article moved under a new PMC ID); if the bucket lists it again, the flag is cleared and the
    automated decision applies. Ingestion reports such runs as `withdrawn`.
15. **Evidence and decision commit together** (fix round 1). Ingestion does every network request
    first, then writes the metadata, licence records, content and gate decision in one
    transaction, so a crash between them cannot leave a version approved on licence records it
    no longer has. A failed XML download still records the metadata (the version stays pending)
    before the worker retries.
16. **`X-Forwarded-Proto` is trusted only when `DJANGO_TRUST_PROXY_SSL_HEADER=true`** (fix round
    1), which should be set only behind a platform proxy that sets the header.

## PMC Cloud Service terms and NLM acknowledgement

The bucket README (`https://pmc-oa-opendata.s3.amazonaws.com/README.txt`, read 2026-10-13) sets
these terms. How each is met:

| Term | How ResearchBridge meets it |
|---|---|
| Acknowledge NLM as the source, clearly and conspicuously | Acknowledgement in `backend/README.md`, the test fixtures README and here; **Phase 4 must show it on every PMC-sourced page** (pending). |
| Do not use the PubMed Central wordmark or PMC logo; no confusingly similar marks | None used. Text references to "PMC" as a source are factual. |
| Do not imply NLM/NIH/HHS endorsement | Stated with every acknowledgement. |
| Redistribute only data licensed for redistribution | The licence gate: `TDM` rejected without download; display only on approved, display-permitting licences; per-figure/paragraph overrides. |
| Keep distributed data current, or say clearly that it is not | Only the current version is served; the daily periodic re-check (never-checked versions first) and `recheck_licences` re-read listings and metadata; changed XML (MD5) is re-parsed; licence-code changes are recorded with history and re-gated; an article no longer listed is withheld and queued for review. |
| No warranty; NLM held harmless | Noted; the product must not present PMC data as warranted (Phase 4 terms). |

**Acknowledgement text** (use in the UI): "Full text and metadata from the NIH National Library of
Medicine (NLM) PubMed Central Article Datasets on AWS (https://registry.opendata.aws/ncbi-pmc/),
accessed [date]. Use does not imply endorsement by NLM."

## End-to-end ingestion results (local Postgres, not committed)

Real articles from the PMC bucket, discovered with ESearch, queued with `ingest_pmc` and
processed by the Procrastinate worker (`procrastinate worker --queues ingestion --one-shot`), in
three runs on 2026-10-13 against the `rb-phase2` database. The first run used `--licence any`
(so author manuscripts were included), the later two `--licence cc-by`. The exact query strings
were not saved in the logs; they were biomedical topic queries restricted to recent years. Counts
are from `manage.py corpus_stats` after the last run (`data/logs/corpus-stats-final.json`).

| | Count |
|---|---|
| Articles ingested (papers / current versions) | **241** |
| Approved (displayable) | **197** |
| Rejected outright (`TDM` author manuscripts; XML never downloaded) | **44** |
| Versions in licence review | 0 |
| Rewriteable papers (approved minus ND/NC-ND) | 158 |
| Retracted | 0 |
| Author manuscripts among them (`is_manuscript`) | 61 (44 TDM, 17 under a CC licence) |

Approved by licence: CC BY 133, CC BY-NC-ND 38, CC BY-NC 22, CC0 2, CC BY-NC-SA 1, CC BY-ND 1.

Parts: 7,776 displayable paragraphs; 1,094 figures and tables, of which 1,072 approved and
**22 queued for figure-level licence review** (their own `<permissions>` blocks with prose-only or
conflicting licence statements, e.g. third-party copyright). Those 22 are excluded by
`Figure.objects.displayable()` while their papers remain displayable.

The worker logs show no failed jobs; three PMC IDs returned by ESearch had no prefix in the bucket
yet and were reported as `not-in-bucket` (not stored).

## Pending the owner

- **Hosting:** create the Render or Railway account and project (web, worker, Postgres with
  pgvector), and set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and (behind the
  platform's HTTPS proxy) `DJANGO_TRUST_PROXY_SSL_HEADER=true` and `DJANGO_SECURE_SSL_REDIRECT=true`
  there. Every setting is listed in `.env.example`. The image
  and its commands are ready; no hosting account was used.
- **Cloudflare R2:** not used yet. Source XML is cached locally in `data/`; storing source files
  in R2 needs an account and bucket (§1.6).
- **Review queue:** create a superuser and work through the open figure reviews in the admin.
- **Seed corpus:** Plan.md asks for "a few thousand" papers chosen to cover common lay searches.
  The machinery is ready; the topic list is an editorial choice for the owner.
- **Output-licence policy** (from Phase 0): rewrites mirror the source licence; confirm or change.
- **psycopg is LGPL-3.0** (deviation 2): docs/conventions.md says permissive licences for every
  direct dependency. Please confirm the exception, ideally as a numbered decisions.md entry such
  as "LGPL libraries may be used unmodified and dynamically imported as dependencies; their source
  is never copied or modified". It was not added to decisions.md on your behalf.
- **Retracted papers** (deviation 6, decided in fix round 2): shown with a retraction notice,
  never rewritten. Nothing needs doing; if you prefer to hide them, deviation 6 names the one
  condition to add. Consider recording the policy in decisions.md.
- **Withdrawn articles:** any article the bucket stops listing appears in the review queue
  ("no longer listed by the source"); decide whether to keep or reject each one.

## Known limitations

- Europe PMC, arXiv and bioRxiv evidence is supported by precedence and the schema, but only PMC
  ingestion exists. arXiv (OAI-PMH + HTML) is deferred to after the MVP (Plan.md).
- No Crossref/Retraction Watch retraction source yet (Phase 5); PMC's flag is the only one.
- ALI embargo dates are honoured when the gate runs; nothing schedules a re-run on the exact date
  (the daily re-check and `recheck_licences --offline` cover it in practice).
- The static access check covers ordinary Django access patterns, not deliberate evasion.
- PMC media (figure images, PDFs) are not downloaded; figures are stored as captions, labels and
  licence data. Image storage belongs with R2.
- Postgres full-text search and vector columns are not added yet (search is Phase 4).
- HSTS is not configured. `DJANGO_SECURE_SSL_REDIRECT` can be set through the environment, but
  `SECURE_HSTS_SECONDS` should be chosen once the production domain and its TLS setup exist
  (`manage.py check --deploy` flags both until then).
- The backend tests need a running Postgres (`make db-up`); there is no SQLite fallback, because
  the constraints and the queue rely on Postgres.
- Text removal on rejection is version-level. A figure or paragraph rejected by its own
  `<permissions>` (inside an approved paper) is never served, but its caption or text stays
  stored, because deleting parts of a version would break the stable IDs the rest of it uses.
- When a rejected version's text is removed, its annotations stay but lose their paragraph link
  (they keep `paragraph_stable_id`); nothing re-attaches them if the text later returns. Licence
  reviews of removed figures and paragraphs are kept (fix round 2); they lose their link to the
  part row and are matched by `part_stable_id` instead.
- After a reviewer approves a version whose text was removed, it stays `pending` until the worker
  runs the ingestion job queued at that moment (fix round 2). Without a running worker it waits.
- Only the cached XML at the current metadata's URL is deleted on rejection. The URL embeds the
  MD5, so a copy of an *older* XML of the same version (downloaded before the publisher replaced
  the file) can remain in `data/http-cache/` until deleted by hand.
- Retraction notices are a read-API contract (`access.retraction_notice`) until Phase 4 renders
  them; nothing serves papers to readers before then.

## Fix round 1 (review findings)

| Finding | What changed |
|---|---|
| C-C1, C-C7: an article removed from the bucket stayed displayable and was re-queued daily | `ingest_pmc_article` marks the stored current version `source_withdrawn_at`, records `last_checked_at`, and the gate sends it to review (deviation 14). Outcome `withdrawn`. Tests: gate and pipeline (withdraw, re-check, relist). |
| C-C2, C-C7: never-checked versions were starved in `stale_pmcids` | Ordered `NULLS FIRST`, then by primary key; the test now includes a never-checked version that must come first. |
| C-C3: evidence and decision were written in separate transactions | One transaction after all network requests (deviation 15). Test: a simulated crash before the gate leaves the old evidence and decision together. |
| C-C4: the NCBI API key could appear in error messages | `search_pmc` re-raises fetch errors with the key redacted and without the chained exception. Test included. |
| C-C5: rejected versions kept their text | The gate removes the text of any rejected version, keeping the article-level evidence (decision 7, `corpus/retention.py`). Tests: JATS all-rights-reserved, reviewer rejection, and text fetched again once the gate stops rejecting. |
| C-C6: inaccurate notes | `to_w3c()` claim removed; the Admin row lists what is registered. |
| C-C9: `X-Forwarded-Proto` trusted unconditionally | Behind `DJANGO_TRUST_PROXY_SSL_HEADER` (default false); tested in `envconfig`. |
| C-C10, S-L1: LGPL psycopg exception | Listed under "Pending the owner" for an explicit decision; not written into decisions.md on the owner's behalf. |
| S-C1: retracted papers stay displayable | Owner decision; listed under "Pending the owner" with the one-line alternative. Behaviour unchanged. |
| S-D1: settings missing from `.env.example` | Added `DJANGO_CSRF_TRUSTED_ORIGINS`, `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_TRUST_PROXY_SSL_HEADER`, `DJANGO_STATIC_ROOT`, `RB_DB_CONN_MAX_AGE`, `RB_LOG_LEVEL`. |
| S-S1: few block comments in tests | Arrange/act/assert comments in the longer tests; comments in `corpus_stats()` and the worker tasks. |
| S-H1: build evidence | See "Final verification". |
| C-C8: no root `.dockerignore` | Not changed: `backend/Dockerfile.dockerignore` is the ignore file BuildKit uses for `-f backend/Dockerfile` (it takes precedence over a root `.dockerignore`), and it already excludes `.venv`, `data`, `.worktrees`, caches, tests and `backend/staticfiles` by allow-listing only `requirements/backend.txt`, `libs/rbcore/` and `backend/`. The rebuild in this round sent a 122 kB context (the local `.venv` alone is 266 MB) and the image has no `/src/backend/tests`. |

`corpus_stats` also reports content states and withdrawn versions now. Migration
`corpus/0003_version_withdrawal_and_removed_content` adds `source_withdrawn_at` and the `removed`
content state.

## Fix round 2 (review findings)

| Finding | What changed |
|---|---|
| S-C1: retracted papers displayable | Decided: shown with a retraction notice, never rewritten (deviation 6 gives the reasons). New `access.retraction_notice()` / `RetractionNotice` make the notice part of the read API; the pipeline retraction test checks it appears and clears with the flag. |
| R-N3: resolved part reviews deleted with the text | `LicenceReview.figure` and `.paragraph` are `SET_NULL`; reviews keep `part_stable_id` and are matched by it. `retention.delete_parts()` (used by text removal and re-parsing) supersedes open part reviews before deleting the parts. Database constraints: one open review per (version, scope, stable ID); an open part review must still link its part. Migration `corpus/0004_review_part_survives_text_removal` copies the stable IDs (checked on the local corpus: all 22 open figure reviews filled). Test: a resolved figure review survives a rejection and applies again when the same text returns; an open one is superseded. |
| R-N1: rejected XML stayed in the download cache | `PmcBucket.forget_xml()`; `ingest_pmc_article` calls it whenever the gate rejects. A reviewer's rejection does the same through the receiver below. Tests in `test_pmc.py`, `test_pipeline.py` and `test_receivers.py`. |
| R-N4: an approved removed version waited for the re-check | `resolve_review` sends `corpus.signals.review_resolved`; `ingestion/receivers.py` queues an ingestion job on commit when the version's text was removed and it is no longer rejected (the corpus app does not import ingestion). Tests in `test_receivers.py`. |
| R-N2: test name did not match the test | Renamed to `test_reviewer_rejection_removes_text_and_new_evidence_brings_it_back`; reviewer approval of a removed version is tested in `test_receivers.py`. Through `ingest`, conflicting new evidence re-fetches the text in the same run, so a removed version only reaches a reviewer by offline re-evaluation. |
| S-L1: inventory said every direct dependency is permissive | The inventory's rule now names psycopg as the one recorded exception awaiting confirmation. |
| C-C10: no decisions.md entry for LGPL | Left to the owner (still under "Pending the owner"). decisions.md is the owner's spec. |

## Final verification

From a fresh `.venv` (`rm -rf .venv && make setup`) with cleared caches and the `rb-phase2`
database on port 5433: `make check` passed (ruff lint and format, docstring and lock checks, mypy
on backend, rbcore and tools, and pytest with 252 backend cases, 257 rbcore and 11 tools).
`docker build -f backend/Dockerfile .` succeeded on the second attempt (the first, at 04:00, timed
out pulling the base image with `DeadlineExceeded`; the retry built all 13 steps), and the image
ran `django-admin check --deploy` as the unprivileged `app` user. The database counts above were re-read from the live database with
`corpus_stats` before shutdown and matched. `docker compose -p rb-phase2 down` was run at the end; the
named volume keeps the ingested corpus locally.

Fix round 1 (2026-10-13, evening): from a fresh `.venv` (`rm -rf .venv` plus every cache, then
`make setup`), `make check` passed: ruff lint and format, docstring and lock checks, mypy on
backend, rbcore and tools, and pytest with 260 backend cases (145 test functions), 257 rbcore and
11 tools. `docker build -f backend/Dockerfile .` succeeded (log in the gitignored
`data/logs/docker-build.log`, which now holds this build), and `django-admin check --deploy` in
the image, with `DJANGO_SECURE_SSL_REDIRECT` and `DJANGO_TRUST_PROXY_SSL_HEADER` set, reported
only the expected HSTS warning (`data/logs/docker-check-deploy.log`). On the local corpus, the new
migration applied cleanly; `recheck_licences --offline` recomputed all 241 versions with 0
changes, and `corpus_stats` matched the counts above; a live `recheck_licences --sync` of three
stored articles (two approved, one TDM) reported all three `unchanged`.
`docker compose -p rb-phase2 down` was run at the end.

Fix round 2 (2026-10-13, night): from a fresh `.venv` (`rm -rf .venv` plus every cache, then
`make setup`), `make check` passed: ruff lint and format, docstring and lock checks, mypy on
backend, rbcore and tools, and pytest with 266 backend cases, 257 rbcore and 11 tools. On the
local corpus, migration `corpus/0004` applied cleanly and `recheck_licences --offline` recomputed
all 241 versions (197 approved, 44 rejected) with 0 changes. The backend image was not rebuilt
(no dependency or Dockerfile change). `docker compose -p rb-phase2 down` was run at the end.
