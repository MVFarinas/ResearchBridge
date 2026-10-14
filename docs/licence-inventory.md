# Licence inventory

The single place where every reused project, dependency, model and data source is recorded
**before** it is used (Plan.md Phase 0; decisions.md §1.6). Seeded on 2026-10-13 from the licence
tiers in [reports/Prior art and reusable open source.md](../reports/Prior%20art%20and%20reusable%20open%20source.md);
those rows are as reported there unless a "verified" note says otherwise.

Rules (details in [conventions.md](conventions.md#reusing-other-peoples-code)): permissive only
(MIT, BSD-2/3, Apache-2.0, ISC, CC0, public domain); AGPL and GPL are reference-only (GPL tools may
run offline as validators); non-commercial, no-derivatives and unlicensed code, weights or data are
forbidden; weights and data are checked separately from code.

**How used** values: `dependency` (installed from a registry, pinned in a lock file),
`vendored` (copied unchanged), `adapted` (copied and modified), `service` (called over an API or
run as a container), `planned` (not used yet), `reference only` (read for ideas, never copied),
`forbidden`.

## 1. In use now

| Project | Code licence | Weights / data licence | Version pinned | How used | Notes |
|---|---|---|---|---|---|
| lxml | BSD-3-Clause | — | 6.1.3 | dependency (rbcore) | JATS parsing, hardened parser options. Bundles libxml2/libxslt (MIT). |
| httpx | BSD-3-Clause | — | 0.28.1 | dependency (rbcore) | `rbcore.http.PoliteFetcher`. |
| anthropic (Python SDK) | MIT | API use governed by Anthropic's commercial terms | 1.13.0 | dependency (optional extra `rbcore[anthropic]`, in dev lock) | `rbcore.llm.AnthropicClient`; never called without a key. Pulls in httpx2 (BSD-3-Clause) and pydantic (MIT). |
| pip-tools | BSD-3-Clause | — | 7.6.2 | dependency (dev) | Lock file compilation (`make lock`). |
| ruff | MIT | — | 0.17.0 | dependency (dev) | Lint and format. |
| mypy | MIT | — | 2.4.0 | dependency (dev) | Type checking. |
| pytest | MIT | — | 9.1.1 | dependency (dev) | Tests. |
| types-lxml | Apache-2.0 | — | 2026.2.16 | dependency (dev) | lxml type stubs for mypy. |
| pgvector/pgvector Docker image | PostgreSQL Licence (PostgreSQL and pgvector); image build files MIT | — | `0.8.7-pg16` | service (local dev database) | `docker-compose.yml`. |
| actions/checkout, actions/setup-python, actions/setup-node | MIT | — | v7.0.1 `3d3c42e`, v7.0.0 `5fda3b9`, v7.0.0 `8207627` (SHA-pinned) | service (CI) | `.github/workflows/ci.yml`. |
| Django | BSD-3-Clause | — | 5.2.18 (5.2 LTS) | dependency (backend) | Web framework, ORM, migrations, admin (Phase 2). |
| psycopg (+ psycopg-binary, psycopg-pool) | **LGPL-3.0-only** | psycopg-binary wheels bundle libpq (PostgreSQL Licence) and OpenSSL (Apache-2.0) | 3.3.6 / 3.3.6 / 3.3.3 | dependency (backend), used unmodified | The PostgreSQL driver Django and Procrastinate both require; no permissive driver is supported by Django's ORM. Recorded deviation from "permissive direct dependencies only" (docs/phase-notes/phase-2.md): LGPL as an unmodified, dynamically imported library imposes no obligation on our code; never copy or modify its source. |
| Procrastinate | MIT | — | 3.10.0 | dependency (backend) | Postgres-backed task queue for the worker (`procrastinate.contrib.django`). Choice recorded in docs/phase-notes/phase-2.md. Pulls in croniter (MIT), attrs (MIT), python-dateutil (Apache-2.0 or BSD-3), asgiref (BSD-3-Clause). |
| defusedxml | PSF-2.0 (Python Software Foundation License; permissive) | — | 0.7.1 | dependency (backend) | Safe parsing of PMC bucket listings (no entities, DTDs or network). |
| gunicorn | MIT | — | 26.2.0 | dependency (backend image) | WSGI server in `backend/Dockerfile`. |
| WhiteNoise | MIT | — | 6.12.0 | dependency (backend image) | Serves the admin's static files. |
| pytest-django | BSD-3-Clause | — | 4.14.0 | dependency (dev) | Backend tests against Postgres. |
| django-stubs, django-stubs-ext | MIT | — | 6.1.2 | dependency (dev) | mypy plugin and stubs for Django. Pulls in types-pyyaml (Apache-2.0). |
| types-defusedxml | Apache-2.0 | — | 0.7.0.20260504 | dependency (dev) | defusedxml stubs for mypy. |
| python Docker image | PSF-2.0 (Python), Debian packages under their own free licences | — | `3.12-slim-bookworm` (tag) | service (backend image base) | `backend/Dockerfile`. |
| Django REST framework (djangorestframework) | BSD-3-Clause | — | 3.18.3 | dependency (backend) | The reader API (Phases 4-5): views, input validation, scoped throttles. |
| djangorestframework-stubs | MIT | — | 3.18.1 | dependency (dev) | mypy stubs for DRF. |
| Next.js (next) | MIT | — | 16.4.0 | dependency (web) | The reader (App Router, server rendering). Pulls in sharp as an **optional** dependency for image optimisation, whose prebuilt libvips binaries are LGPL-3.0-or-later; the app does not use `next/image`, and the binaries are installed unmodified (same posture as psycopg). Telemetry: set `NEXT_TELEMETRY_DISABLED=1`. |
| React, React DOM | MIT | — | 19.3.0 | dependency (web) | UI. |
| @recogito/text-annotator | BSD-3-Clause (LICENSE verified at `0d375b0`, the npm gitHead of 4.3.7) | — | 4.3.7 | dependency (web), bundled into browser JS | Read-only highlighting of annotations on the original text (Phase 4). Licence text in `third_party/recogito-text-annotator/` for the bundled-distribution notice. Pulls in @annotorious/core (BSD-3-Clause, 3.9.4; text in `third_party/annotorious-core/`), rbush, dequal, nanoevents, colord, uuid, debounce, poll, hotkeys-js (MIT). The React wrapper (`@recogito/react-text-annotator`) is not used: it pulls in OpenSeadragon and the TEI extension. |
| TypeScript | Apache-2.0 | — | 6.0.3 | dependency (web, dev) | Strict type checking. 7.x was not used: typescript-eslint supports `<6.1`. |
| ESLint | MIT | — | 9.39.5 | dependency (web, dev) | Lint. 10.x not used: eslint-plugin-react (via eslint-config-next) supports `^9.7`. |
| eslint-config-next | MIT | — | 16.4.0 | dependency (web, dev) | Next.js, React, hooks, jsx-a11y and TypeScript rules. Transitive axe-core (MPL-2.0) and lightningcss (MPL-2.0) are dev-only build/lint tools, unmodified. |
| eslint-plugin-jsdoc | BSD-3-Clause | — | 65.3.2 | dependency (web, dev) | Enforces TSDoc comments on exports. |
| Vitest | MIT | — | 5.0.4 | dependency (web, dev) | Unit and component tests. |
| @vitejs/plugin-react | MIT | — | 6.1.2 | dependency (web, dev) | JSX for Vitest. |
| jsdom | MIT | — | 30.1.2 | dependency (web, dev) | DOM for component tests. |
| @testing-library/react, /dom, /jest-dom, /user-event | MIT | — | 16.3.3, 10.4.2, 7.0.1, 14.6.8 | dependency (web, dev) | Component tests. |
| @types/react, @types/react-dom, @types/node | MIT | — | 19.3.0, 19.3.0, 24.19.2 | dependency (web, dev) | Type declarations. |
| @playwright/test | Apache-2.0 | Chromium headless shell (BSD-3-Clause and others; downloaded into `web/node_modules`, never committed) | 1.64.0 | dependency (web, dev) | Optional smoke test against a running stack (`npm run test:e2e`); not in CI. |

Transitive Python dependencies are pinned in [requirements/dev.txt](../requirements/dev.txt);
transitive npm dependencies in [web/package-lock.json](../web/package-lock.json) (audited
2026-10-13: MIT, ISC, BSD, Apache-2.0, BlueOak, 0BSD, CC0 and MIT-0 throughout, plus the
exceptions named in the rows above, caniuse-lite's CC-BY-4.0 browser data and spdx-exceptions'
CC-BY-3.0 list, both dev-only data used unmodified).
Transitive dependencies under weak, file-level copyleft (MPL-2.0, e.g. certifi 2026.7.22 via
httpx and pathspec 1.1.1 via mypy) are acceptable when installed and used unmodified; never copy
or modify their source. The permissive-only rule above still applies to every direct dependency
and to all copied code, with one recorded exception awaiting the owner's confirmation: psycopg
(LGPL-3.0, row above), the PostgreSQL driver Django and Procrastinate require, used unmodified as
an imported library (docs/phase-notes/phase-2.md, deviation 2).

### Evaluated and not used

| Project | Code licence | Version reviewed | Decision |
|---|---|---|---|
| Celery | BSD-3-Clause | 5.6.3 (PyPI) | **Not used** for the worker (Phase 2): it needs a separate broker (Redis or RabbitMQ), a second service to host and pay for, which §1.6's "fewest moving parts" argues against. |
| django-q2 | MIT | 1.11.1 (PyPI) | **Not used** (Phase 2): can use the Django ORM as its broker, but by polling, without Postgres-native locking or LISTEN/NOTIFY. |
| django-tasks | BSD-3-Clause | 0.12.0 (PyPI) | **Not used** (Phase 2): the reference backend for Django's new tasks API; its database backend is pre-1.0. Worth revisiting when the backend moves to Django 6.x. |
| dj-database-url | BSD-3-Clause | 3.1.2 (PyPI) | **Not used** (Phase 2): parsing one PostgreSQL URL is a few tested lines (`rb_backend.envconfig`). |
| pyalex | MIT | 0.21 (PyPI, read 2026-10-13) | **Not used** (Phases 4-5): it fetches with `requests` outside `rbcore.http.PoliteFetcher` (so outside the shared rate limits, size limits and neutral User-Agent rule) and keeps the API key in global state. Two OpenAlex endpoints are a small client over the fetcher we already have (`rb_backend.metadata.openalex`). |
| @recogito/react-text-annotator | BSD-3-Clause | 4.3.7 (npm) | **Not used** (Phase 4): the plain `@recogito/text-annotator` in a small client component suffices; the wrapper pulls in OpenSeadragon and the TEI/XML extension. |
| Hypothesis client anchoring (`src/annotator/anchoring`) and approx-string-match | BSD-2-Clause; MIT | not taken | **Not used** (Phase 4): the API serves annotations only while their paragraph text is unchanged, so exact matching (position, then quote with prefix/suffix) is enough; nothing was copied. Revisit for the §1.2 browser extension, where pages are messy. |
| pubmed_parser | MIT | 0.5.1 (PyPI sdist) | **Not used** for `rbcore.jats` (Phase 0). It parses with lxml's default parser (no hardening against entities or network), uses bare `except` and `print`, flattens only one level of inline markup, returns flat paragraphs with no stable IDs or nested sections, and does not record which field a licence came from. Its approach to matching COI footnotes by attribute value informed ours; no code was copied. |

## 2. Planned: permissive, attribution only

| Project | Kind | Code licence | Weights / data licence | Version pinned | How used | Notes |
|---|---|---|---|---|---|---|
| allofplos | PLOS bulk download | MIT | PLOS content CC BY | — | **not used** (Phase 2) | PLOS deposits its articles in PMC, so they arrive through the PMC bucket under the same `license_code` gate; the 7 GB zip would add a second pipeline. PLOS coverage in the bucket was not measured (docs/phase-notes/phase-2.md). |
| LaTeXML | arXiv LaTeX to HTML | Public domain | — | — | planned (after MVP) | |
| ar5iv | arXiv HTML | MIT | per-paper licence | — | planned (after MVP) | |
| GROBID | PDF fallback | Apache-2.0 | — | — | planned | |
| Docling | PDF fallback (§1.2 uploads) | MIT | models Apache-2.0 (Heron, Granite-Docling) | — | planned (Phase 6) | |
| olmOCR | PDF fallback | Apache-2.0 | Apache-2.0 | — | planned | |
| @recogito/pdf-annotator | PDF passage anchoring | BSD-3-Clause | — | — | planned (Phase 6 uploads) | The text annotator is in use (section 1). |
| pdf.js | PDF rendering | Apache-2.0 | — | — | planned (Phase 6) | |
| Hypothesis client (anchoring modules) | Anchoring | BSD-2-Clause + MIT subcomponent | — | — | planned, **pending review** (§4) | |
| Hypothesis h | Annotation server | BSD-2-Clause | — | — | reference for moderation design | Not self-hosted (§1.6). |
| PaperQA2 (paper-qa) | Cited extraction (F3) | Apache-2.0 | — | — | planned (Phase 3) | |
| Kotaemon | Grounded QA | Apache-2.0 | — | — | reference | |
| open-notebook | Grounded QA | MIT | — | — | reference | |
| ResearchHub backend | Votes, reputation | MIT | — | — | planned reference / possible adaptation (Phase 7) | Check coupling to its token economy first. |
| Remark42 | Comments | MIT | — | — | planned option (Phase 7) | |
| Coral (talk) | Comments | Apache-2.0 | — | — | planned option (Phase 7) | |
| Isso | Comments | MIT | — | — | planned option | |
| AlignScore | Faithfulness metric | MIT | check checkpoint licence before use | — | planned (Phase 1 baseline) | |
| SummaC | Faithfulness metric | Apache-2.0 | check checkpoint licence | — | planned (Phase 1 baseline) | |
| QAFactEval | Faithfulness metric | BSD-3-Clause | check checkpoint licence | — | planned (Phase 1 baseline) | |
| FActScore | Faithfulness metric | MIT | — | — | reference | |
| MiniCheck | Faithfulness metric | Apache-2.0 | RoBERTa / DeBERTa / Flan-T5 checkpoints MIT | — | planned (Phase 1 baseline) | **Not** Bespoke-MiniCheck-7B (CC BY-NC). |
| Vectara HHEM | Hallucination model | — | Apache-2.0 | — | planned option | |
| pszemraj/long-t5-tglobal-base-sci-simplify | Simplifier baseline | — | Apache-2.0 | — | planned (baseline only) | |
| scrutiny | GRIM/DEBIT checks | MIT | — | — | planned (internal triage only, §2.3) | |
| PersonalizedJargon | Jargon familiarity | Apache-2.0 | — | — | planned (Track R) | |
| definition-complexity | Definitions | Apache-2.0 | — | — | planned (Track R) | |

### Safe but stale: fork and own if used

| Project | Code licence | Notes |
|---|---|---|
| PaperMage | Apache-2.0 | Stale. |
| PaperCraft (allenai/pdf-component-library) | Apache-2.0 declared in npm only | **Pending review** (§4). |
| ScholarPhi | Apache-2.0 | Last commit March 2023; needs LaTeX and PostgreSQL. |
| react-pdf-highlighter | MIT | Stale. |
| RRnlp | MIT (per report) | Stale. |
| SciTLDR | Apache-2.0 (per report) | Stale. |

## 3. Data and API sources

| Source | Terms | How used | Obligations |
|---|---|---|---|
| PMC Cloud Service (`s3://pmc-oa-opendata`) | Per-article licence (`license_code`); bucket terms | **in use** (Phase 2 ingestion, HTTPS, no credentials); fixtures (Phases 0, 2) | Acknowledge NLM; no PMC logo or implied endorsement; redistribute only licensed data; keep it current or say it is not; honour `is_retracted`. `TDM` = never ingest. |
| Europe PMC REST | Per-article licence; free API | fixtures (Phase 0); planned | Its `fullTextXML` copy can lack the machine-readable licence that PMC's copy has (see fixtures); prefer the PMC copy. |
| PLOS (journals.plos.org, allofplos) | CC BY 4.0 (some CC0) | fixture (Phase 0); ingested via PMC (Phase 2) | Attribution. |
| arXiv OAI-PMH and API | Metadata CC0; per-paper licence; API ToU | planned (after MVP) | At most 1 request per 3 s. Non-exclusive licence = no display. |
| bioRxiv / medRxiv API | Per-preprint licence | planned | `cc_no` = never ingest. |
| NCBI E-utilities | NLM terms | **in use** (Phase 2: ESearch discovery for `ingest_pmc`) | At most 3 requests/s without a key (10 with `NCBI_API_KEY`). `tool=researchbridge`; no e-mail address is sent. |
| OpenAlex | CC0 | **in use** (Phases 4-5): search and per-paper citation metrics, `rb_backend.metadata.openalex`; keyless unless `OPENALEX_API_KEY` is set | Usage-based pricing since Feb 2026 (single works free, search metered); every answer cached in Postgres and shown with its "as of" date. Licence fields are secondary signals only. |
| OpenCitations | CC0 | planned | |
| NIH iCite | Public domain | **in use** (Phase 4): citations by year and RCR for papers with a PMID | Cached with "as of" dates. |
| Crossref (incl. Retraction Watch data) | Metadata open; Retraction Watch citation requested | **in use** (Phase 5): `updated-by` notices (retraction, expression of concern, correction) per DOI | Retraction Watch is cited in the credibility panel and the site footer. No `mailto` is sent. Licence fields are secondary signals only. |
| NCBI PMC ID Converter | NLM terms | **in use** (Phase 5): DOI/PMID to PMC ID for lookup | `tool=researchbridge`, no e-mail address; at most 3 requests/s. |
| DOAJ | CC0 metadata | planned (discovery only) | Licence is journal-level, never the gate. |
| PLOS and eLife lay-summary datasets (HF `tomasg25/scientific_lay_summarisation`) | CC BY 4.0 (card) | planned (Phase 1) | Re-check each paper's licence at its primary source. |
| PLABA | CC0 | planned (Phase 1) | |
| FactPICO annotations | CC BY 4.0 | planned (Phase 1, judge calibration) | |
| Claude API | Anthropic commercial terms | planned (key not yet provisioned) | No-training / minimal retention settings for §1.2 uploads. |

## 4. Pending licence reviews

These two are on the "safe" list but need a recorded decision before any code is copied or
depended on. Evidence gathered on 2026-10-13; the decision is the owner's.

| Project | Observed | What to decide | Steps |
|---|---|---|---|
| **Hypothesis client** (`hypothesis/client`) | GitHub reports `NOASSERTION`. The `LICENSE` at `main` (commit `b4d085a`, checked 2026-10-13) is BSD-2-Clause (© 2013-2019 Hypothes.is Project and contributors) followed by a "Subcomponents" section granting the **annotator** subcomponent under MIT (© 2012 Aron Carroll, Rufus Pollock, Nick Stenning). Both are permissive. | Whether to adapt the anchoring modules (`src/annotator/anchoring`), and which commit. | 1. Pick the commit to take. 2. Re-read `LICENSE` at that commit and confirm no other subcomponents apply to the files taken. 3. Copy with headers, put the full `LICENSE` text (both parts) in `third_party/hypothesis-client/LICENSE`. 4. Change this row to `adapted`. |
| **PaperCraft** (`allenai/pdf-component-library`, npm `@allenai/pdf-components`) | The repository has **no LICENSE file** (GitHub licence: none; last push 2024-02-15). npm `@allenai/pdf-components@1.0.2` declares `"license": "Apache-2.0"` in its package metadata. | Whether the npm declaration is enough to rely on. | 1. Prefer depending on the published npm package (whose metadata grants Apache-2.0) over copying from the repository. 2. If copying is wanted, ask the maintainers (allenai) to add a LICENSE file, or get written confirmation; until then treat the repository as **unlicensed** for copying. 3. Record the outcome here. |

## 5. Reference only: copyleft (never copy; GPL may run offline as a validator)

| Project | Licence | Why it is interesting |
|---|---|---|
| rtransparent | GPL-3 (imports AGPL ODDPub) | COI / funding / registration extraction; offline validator only. |
| statcheck | GPL-3 | p-value recomputation; offline only. |
| RobotReviewer | GPL-3 | Risk-of-bias models (dormant since 2022). |
| Discourse | GPL-2 | Reputation design. |
| Manifold, PubPub | GPL | Annotation and publishing UIs. |
| Open Paper (khoj-ai/openpaper) | AGPL-3.0 | Closest live analogue to F2/F3. |
| PDFMathTranslate, BabelDOC | AGPL-3.0 | Closest analogue to F1 (layout-preserving rewrite). |
| ODDPub | AGPL-3.0 | Open data detection. |
| Lemmy, OpenReview-web | AGPL-3.0 | Discussion. |
| CERMINE | AGPL-3.0 | PDF metadata extraction. |
| MinerU2.5 VLM weights | AGPL-3.0 (tagged) | — |

## 6. Forbidden: non-commercial, no-derivatives, or no licence

| Project | Kind | Licence | Note |
|---|---|---|---|
| ChatPaper | code | CC BY-NC-ND | |
| Bespoke-MiniCheck-7B | weights | CC BY-NC | Use MiniCheck's MIT checkpoints instead. |
| Nougat | weights | CC BY-NC (code MIT) | |
| Marker / Surya | weights | OpenRAIL-M variant (free only under $5M funding/revenue) | Excluded per §1.6. |
| MinerU | weights / code conditions | Apache-2.0 plus attribution and commercial thresholds | Excluded per §1.6. |
| OpenScholar-8B | weights | Llama 3.1 licence | Obligations attached; not planned. |
| LLM-AggreFact | dataset | CC BY-ND | Never redistribute anything derived from it. |
| Semantic Scholar API, S2ORC access | API | Licence forbids embedding for commercial gain; revocable | |
| SCImago SJR | data | Prior written permission required | |
| scite, Altmetric, Dimensions | data | Paid contracts | |
| Paper Plain | code | none | Design reference only (user study is useful). |
| Scim, BAGELS, LimGen, LENS, Devaraj factuality code, pdf.js-hypothes.is | code | none | |
| MedReadMe | data | none | Ask the authors before any use. |
| De-Jargonizer | code | none | Reimplement from the published method (Track R). |
| Cochrane and SciNews texts | data | third-party copyright despite CC BY tags | |
