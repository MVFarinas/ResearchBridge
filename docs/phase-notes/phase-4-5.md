# Phases 4-5 — Reader app, search and lookup: notes

Branch `phase-4-5-reader-search` (from `phase-2-corpus-licence-gate`), built 2026-10-13 in an
unattended run. Plan.md "Phase 4" and "Phase 5"; decisions.md §1.1 (attribution on every page),
§1.3 (annotation provenance and disclaimers), §1.5 (entry points), §1.6 (stack), §2.3 (paper-level,
neutral signals only).

**There is no generation yet** (no API key; Phase 3 has not run), so no plain-English rewrite,
LLM annotation or appraisal summary exists for any paper. The API reports that state and the
reader shows honest empty states; nothing generated is faked. The only annotations, rewrites and
metrics in this branch that are not real are test data and the development-only demo, all named
synthetic.

## What was built

### Backend (`backend/`)

| Area | What | Where |
|---|---|---|
| Search index | `SearchDocument` (one per version): weighted `tsvector` (title A, abstract B, authors and journal C) with a GIN index, plus `published_year` for filters. **Rebuilt by the gate** at the end of every `evaluate_version`, so it follows ingestion, re-checks and review resolutions. Only abstract paragraphs whose own licence allows display are indexed. Read only through `displayable()` (the access check now covers `SearchDocument`). `manage.py rebuild_search_index` backfills. | `corpus/models/search.py`, `corpus/search_index.py`, `corpus/gate.py` |
| Access layer additions | `displayable_search_documents`, `article_copyright` (copyright lines for the attribution block), `withheld_parts` (counts, never content, of parts held back by their own licence), `ingestion_state` (gate status only, for lookup). | `corpus/access.py` |
| Metadata clients | OpenAlex (work by DOI or PMID; search with year, type and date-sort filters; optional `OPENALEX_API_KEY`, redacted from errors), NIH iCite (citations by year, RCR), Crossref (`updated-by` notices), PMC ID Converter (DOI/PMID → PMC ID). All over `rbcore.http.PoliteFetcher` with per-host intervals (OpenAlex 0.5 s, Crossref and iCite 1 s, NCBI 0.34 s), a 10 s timeout and one retry. 401/402/403/429 become `UpstreamRefusedError`, other failures `UpstreamError`, 404 is a cacheable "not found". Payloads are trimmed to the fields used. | `metadata/` |
| Metadata cache | `CachedResponse` in Postgres: trimmed payload and `fetched_at` ("as of"). Fresh answers are served as is; after the TTL (`RB_METADATA_TTL_HOURS` 168, `RB_SEARCH_TTL_HOURS` 24) the service is asked again, and if it fails the old answer is served **marked stale with its original date**. | `metadata/cache.py`, `metadata/services.py` |
| Credibility | Paper-level and neutral only: OpenAlex citation count, counts by year, FWCI and citation percentile where present, `is_retracted`; iCite citations by year and RCR (with the provisional flag); Crossref retraction, expression-of-concern and correction notices with links and Retraction Watch attribution. Each section has a status (`ok`, `not_found`, `not_applicable`, `unavailable`), source, licence and "as of" date. Nothing about journals or publishers. | `metadata/credibility.py` |
| Crossref research | Checked against live records before coding: the **original article's** record lists notices in `updated-by` (`DOI`, Crossmark `type` such as `retraction`, `partial_retraction`, `withdrawal`, `removal`, `expression_of_concern`, `correction`; `label`; `source` = `retraction-watch` or `publisher`; `updated` date; `record-id` for Retraction Watch); the notice's record has the mirror `update-to`. One lookup per DOI is enough. Examples recorded as fixtures: the retracted Wakefield Lancet paper (correction 2004, retraction 2010) and a Karger paper (expression of concern 2021, retraction 2022). | `metadata/crossref.py` |
| Corpus search | `websearch_to_tsquery` ranking with `ts_rank`; filters by year range and availability; sort by relevance, newest or oldest; snippets from `ts_headline` with private-use highlight markers (no HTML crosses the API). | `discovery/corpus_search.py` |
| Search service | Corpus results plus OpenAlex results; every result has **exactly one** availability tag: `plain_english_available` (corpus, `can_rewrite`), `original_annotations_only` (corpus, display only), `may_be_available` (not in the corpus, OpenAlex reports a CC or public-domain licence and there is an identifier lookup can check; routes to lookup), `original_elsewhere`. An OpenAlex work already in the corpus takes the corpus tag and key. If OpenAlex refuses (e.g. keyless budget spent) or fails, the corpus results come back with a notice. | `discovery/search.py`, `discovery/availability.py`, `discovery/results.py` |
| Lookup | Accepts DOI, PMC ID, PMID, arXiv ID (bare, prefixed or as URLs) or a title. Corpus hit → the paper. Otherwise the ID converter finds the PMC ID and the **primary source** decides: the latest version's `license_code` in the PMC bucket metadata, through the same precedence code as ingestion. Eligible → a `LookupRequest` and a worker job (`queue_ingest`), within `RB_LOOKUP_DAILY_INGEST_LIMIT` (100/day); the status endpoint reports `preparing`, `ready` (with the paper key), `held_for_review`, `not_available` or `failed`. A request is reused while its job waits. Not eligible / not in PMC → "not available here" with DOI, PubMed and Scholar links. Titles return candidates (no guessing). arXiv IDs get arXiv and DOI links (arXiv ingestion is after the MVP). Nothing about the reader is stored. | `discovery/lookup.py`, `identifiers.py`, `ingestion/tasks.py` |
| Retractions from new sources | A Crossref retraction notice (or OpenAlex `is_retracted`) seen during a credibility lookup is recorded on the paper (`crossref:retraction-watch`, `crossref:publisher` or `openalex:is_retracted`, with the notice date), so the paper stops being rewriteable. Never cleared automatically. | `corpus/retractions.py` |
| API | DRF, public and unauthenticated, JSON only, under `/api/v1/`: `papers/<key>/` (metadata, licence, permissions and output licence, attribution with copyright lines and the NLM acknowledgement, declarations, sections and paragraphs, figure captions, withheld counts, annotations in W3C shape with provenance and the disclaimer flag (annotations whose paragraph text changed are withheld), rewrite and summary status, DOI/Scholar/PMC links), `papers/<key>/credibility/`, `search/`, `lookup/` (202 when queued, 503 when a source is down), `lookup/requests/<id>/`. Keys are PMC IDs (`rb-<id>` otherwise); a gated or unknown paper is a 404 either way. | `api/` |
| Rate limits | DRF scoped throttles per client address (`RB_API_RATE_*`: search 30/min, papers 120/min, credibility 60/min, lookup 10/min, lookup status 120/min) on a **database cache table** (`rb_cache`, created by a migration) so limits hold across processes. `RB_API_NUM_PROXIES` defaults to 0 (socket address): DRF's own default would trust any client's `X-Forwarded-For`. | `settings.py`, `api/migrations/0001_cache_table.py` |
| rbcore | `FetchError.status` carries the HTTP status, so callers tell 404 from refusals and outages. | `libs/rbcore/src/rbcore/http.py` |

### Web (`web/`)

Next.js 16.4.0 (App Router), React 19.3.0, TypeScript 6.0.3 strict (`noUncheckedIndexedAccess`),
ESLint 9 with `eslint-config-next` and `eslint-plugin-jsdoc` (TSDoc required on every exported
function, component, type and interface), Vitest 5 with Testing Library and jsdom.

| Route / part | What |
|---|---|
| `/` | Explanation, search box, legend of the four availability tags. |
| `/search` | GET form (works without JavaScript; shareable URLs): query, year range, availability, work type, sort by relevance/newest/oldest. Two sections: "Readable on ResearchBridge" and "From the wider scholarly record" (with OpenAlex's "as of" date or its notice). Snippets are highlighted as text. Pagination. |
| `/papers/<key>` | Server-rendered and indexable: `generateMetadata` gives title, description, canonical URL and Highwire `citation_*` tags. Retraction banner; title, byline, one-line licence statement; **Read original paper** (`https://doi.org/<doi>`) and **Find on Google Scholar** (a search URL, never fetched); view tabs as links (`?view=plain` / `?view=original`). Original view: sections at their heading levels, paragraphs carrying `data-paragraph-id`, figure and table captions, a note for withheld parts, and the annotation layer. Plain-English view: an empty state that says why (not generated yet, or the licence forbids it). Aside: summary panel (empty state plus the paper's own competing-interest and funding statements, quoted) and the credibility panel (streamed in with Suspense, so the text is never held up). The full licence and attribution block, with the NLM acknowledgement, is on every view. |
| Annotation layer | `@recogito/text-annotator` 4.3.7 (BSD-3-Clause), loaded in the browser only when annotations exist, read-only (`annotatingEnabled: false`). API selectors count Unicode code points per paragraph; they are converted to UTF-16 offsets relative to the paragraph element (`offsetReference`), with the quote (and prefix/suffix) as a fallback; an annotation that cannot be placed unambiguously is left out. Explanations are also listed below the text (keyboard and screen-reader reachable) with provenance and the disclaimer for unverified AI text. Superseded annotations are not shown. |
| Side-by-side | `AlignedParagraphs` pairs plain-English paragraphs with originals by paragraph ID: two columns from 70rem, stacked below. Ready for Phase 3 output; used today only by the demo. |
| `Disclaimer` | Ready for LLM output: annotations, rewrites, summaries. |
| `/lookup`, `/lookup/requests/<id>` | Server-action form (progressive enhancement); redirects to the paper or to a status page that refreshes itself every 5 s and redirects when ready. |
| `/methodology` | Says the faithfulness benchmark is pending and describes what it will measure (§1.4). No results. |
| `/dev/annotations-demo` | **Development only**: synthetic paper, synthetic annotations (including one after an emoji, to exercise the offset conversion) and a synthetic rewrite, under a "SYNTHETIC DEMO" banner. `notFound()` when `NODE_ENV` is production, so a production build serves a 404 (checked in a unit test, by the Playwright smoke test against `next start`, and by the CI build). `robots.txt` disallows `/dev/`. |
| Accessibility and mobile | Skip link, landmarks, labelled form controls, visible focus, text labels on tags (not colour alone), live region for the selected explanation, sparkline with a text alternative, light and dark schemes, layouts checked at phone width (Pixel 7) and 1280 px in Chromium screenshots. |

## How to run it locally, end to end

```sh
cd <worktree>
make setup                                        # .venv (Python 3.12) + npm ci in web/
export RB_DB_PORT=5434 DJANGO_DEBUG=true          # any free port; 5433 is the default
make db-up COMPOSE_PROJECT=rb-phase45             # Postgres 16 + pgvector

cd backend
../.venv/bin/python manage.py migrate             # corpus, search index, metadata cache, rb_cache table, queue
../.venv/bin/python manage.py ingest_pmc --sync --limit 20 \
    --query "vitamin D AND supplementation AND 2024[pdat]" --licence cc-by
../.venv/bin/python manage.py rebuild_search_index   # only for versions ingested before this branch
../.venv/bin/python manage.py runserver 127.0.0.1:8000   # the API
../.venv/bin/python manage.py procrastinate worker --queues ingestion   # second terminal: lookups

cd ../web                                         # third terminal
NEXT_TELEMETRY_DISABLED=1 RB_API_URL=http://127.0.0.1:8000 npm run dev   # http://localhost:3000

# Production-mode web and the optional browser smoke test:
NEXT_TELEMETRY_DISABLED=1 npm run build
NEXT_TELEMETRY_DISABLED=1 RB_API_URL=http://127.0.0.1:8000 npm start -- -p 3045
PLAYWRIGHT_BROWSERS_PATH=0 npx playwright install --only-shell chromium   # once, into node_modules
PLAYWRIGHT_BROWSERS_PATH=0 npm run test:e2e

cd .. && make check                               # lint, typecheck, tests (needs the database up)
make db-down COMPOSE_PROJECT=rb-phase45
```

Use `localhost`, not `127.0.0.1`, for `next dev`: Next 16 blocks dev-only resources requested from
another origin, which stops hydration. `OPENALEX_API_KEY` is optional (see "Pending").

## Results of this run (local, not committed)

- **Sample corpus** (database `rb-phase45`, real PMC articles through Phase 2's `ingest_pmc
  --sync`): 60 papers, **51 displayable** (CC BY 47, CC BY-NC 2, CC BY-NC-ND 1, CC BY-ND 1),
  49 rewriteable, 9 TDM author manuscripts rejected without download; 2,531 paragraphs and 287
  figures/tables displayable, 6 figures in licence review (excluded from pages and counted as
  withheld). Queries: vitamin D supplementation 2024 (licence any), adolescent sleep 2025 (CC BY),
  exercise and depression trials 2024 (licence any), lifestyle and hypertension 2025 (CC BY), plus
  one paper (PLOS Medicine, PMC11964404) added end to end through the lookup API and the worker.
  Counts from `corpus_stats` in `data/logs/corpus-stats-phase45.json`.
- **Live checks** (keyless OpenAlex, iCite, Crossref, ID converter; a handful of requests): search
  returned corpus and OpenAlex results with tags; credibility returned all three sources with dates;
  lookup of the PLOS DOI queued a job, the worker ingested it, and the status turned `ready`;
  arXiv and a non-PMC DOI (the Lancet paper) returned "not available here" with links.
- **Production build** (`next build` + `next start`) against the local API: every page rendered;
  a TDM paper is a 404; the demo route is a 404.
- **Playwright smoke test**: 6 passed (3 tests × desktop and phone) — search → paper → licence block
  and as-of dates → plain-English empty state; arXiv lookup; demo 404. Chromium's headless shell
  was downloaded into `web/node_modules` (gitignored); the test is **not** in CI, which has no
  backend or corpus.
- **Docker**: `docker build -f backend/Dockerfile .` succeeded with DRF in the image lock, and
  `django-admin check` inside the image reported no issues (image removed afterwards).

## Decisions, deviations and reasons

1. **The `plain_english_available` tag is kept, but its label is honest.** The API tag follows
   §1.5 (it describes what the licence allows). Until a rewrite exists, the UI labels it "Plain
   English permitted (not written yet)", and each result carries `rewrite_status`, so the reader
   never sees "Plain English available" for a paper without one.
2. **Papers open on the original until a rewrite exists** (Plan.md says the plain-English view is
   the default for `can_rewrite` papers). Defaulting to an empty view would greet every reader with
   "not generated yet"; `chooseView` switches the default as soon as `rewrite.status` is
   `available`.
3. **Two result lists, not one merged list.** Relevance scores from Postgres and OpenAlex are not
   comparable; the corpus list comes first ("Readable on ResearchBridge"), then the wider record.
   Works in both are tagged as corpus papers in the OpenAlex list.
4. **pyalex (MIT) not used**: it bypasses `PoliteFetcher` (shared rate limits, size limits, neutral
   User-Agent) and keeps the key in global state; the client is about 400 lines, mostly docstrings and parsing, over the existing
   fetcher. Recorded under "Evaluated and not used".
5. **No anchoring code was copied.** The Hypothesis client's anchoring (BSD-2) and
   approx-string-match (MIT) were considered: since the API withholds annotations whose paragraph
   text changed, exact matching (position, then quote with prefix/suffix) is sufficient, and the
   converter between code points and UTF-16 is a few tested lines. Revisit for the §1.2 browser
   extension. The only third-party code shipped is through published packages; BSD-3 licence texts
   of the annotator packages bundled into browser JavaScript are in `third_party/`.
6. **Titles list candidates** instead of being resolved to one paper; authors are searchable through
   the same search (the index weights authors). This avoids preparing the wrong paper.
7. **arXiv lookups are not ingested** (Plan.md: arXiv after the MVP); they link to arXiv and the
   arXiv DOI.
8. **Eligibility needs a PMC `license_code` that permits display on its own.** A missing code, a
   code needing review, or `TDM` is "not available here"; the full gate still runs on the complete
   record when the worker ingests an eligible paper. A paper the gate already rejected is reported
   without asking the bucket again.
9. **Credibility is fetched at request time**, not by the worker: single-record lookups are fast
   and free, answers are cached with dates and served stale on failure, and the panel is streamed
   after the text. Metadata requests are serialised per process (a lock) so the per-host intervals
   hold across request threads.
10. **Retractions from Crossref/OpenAlex are written to the paper during a credibility read** (a
    write in a GET path, idempotent). Failing towards "retracted" only withholds a rewrite; it never
    hides the original or the notice. Phase 2 planned these sources for Phase 5.
11. **Rate limits key on the socket address** (`RB_API_NUM_PROXIES=0`). Behind the web server every
    reader shares the server's address until hosting sets the number of trusted proxies (see
    "Pending"); the web forwards `X-Forwarded-For` for that case.
12. **The cache table is created by a migration** (`createcachetable` in `api/0001`), so
    `migrate` alone prepares every environment, including the Docker image and the test database.
13. **Toolchain majors held back for compatibility**: TypeScript 6.0.3 (typescript-eslint supports
    `<6.1`; 7.x is the native compiler) and ESLint 9.39.5 (eslint-plugin-react via
    eslint-config-next supports `^9.7`). Next.js, React, Vitest and the rest are the latest stable.
14. **`next dev` agent files disabled** (`agentRules: false`): Next 16 otherwise writes an
    `AGENTS.md` into `web/`; the repository's `CLAUDE.md` already covers agents.
15. **Figures are captions only.** Images and table bodies are not stored yet (Phase 2: images
    belong with R2); the page says so and links the original.
16. **Superseded annotations are hidden**; the provenance filter (human / LLM / both) is Phase 7.
17. **The Crossref fixture for the Karger paper had its abstract removed** (the text belongs to its
    authors); the manifest marks it modified. All other recorded responses are byte-for-byte.

## Pending the owner

- **OpenAlex key (optional):** without `OPENALEX_API_KEY`, OpenAlex allows a small daily budget
  (the keyless search worked tonight); when it refuses, search falls back to corpus-only with a
  notice. A free key raises the budget; search calls are metered (about $1 per 1,000 beyond the
  free daily allowance), so decide whether to add a key and a spending cap.
- **Hosting:** a web service for Next.js (`npm run build && npm start`) beside the backend and
  worker on Render or Railway. Set `RB_API_URL` (the backend's private address), `RB_SITE_URL`
  (the public origin, for canonical links), `NEXT_TELEMETRY_DISABLED=1`, and on the backend
  `RB_API_NUM_PROXIES` to the number of proxies in front of it **only if** it is reachable solely
  through them (otherwise leave 0). Keep the backend private if possible.
- **Domain:** needed for `RB_SITE_URL`, HSTS (Phase 2 note) and a sitemap.
- **Launch checklist (Plan.md Phase 5):** terms and privacy pages, a takedown/contact route, a
  third-party notices page (the BSD-3 annotator packages are redistributed in browser JavaScript;
  texts are in `third_party/`), a licence audit of a random corpus sample, disclaimer copy review,
  and privacy-respecting analytics (none was added).
- **LGPL binaries:** Next.js pulls in sharp's prebuilt libvips (LGPL-3.0-or-later) as an optional
  dependency; it is unused (no `next/image`) and unmodified. Same question as psycopg in Phase 2.
- **Retraction policy:** papers retracted per Crossref or OpenAlex are now marked automatically and
  never un-marked; confirm, or ask for a review queue for these.

## Known limitations

- No sitemap yet (needs the domain and a list endpoint).
- The search index covers title, abstract, authors and journal, not full text.
- OpenAlex `may_be_available` is a hint: many such works are not in PMC's open-access datasets,
  and lookup then says "not available here".
- The metadata lock serialises outbound metadata requests per process; under heavy load,
  credibility panels for uncached papers queue behind each other (cached ones are unaffected).
- Lookup status depends on Procrastinate's job table; if jobs are pruned, a request with no stored
  paper shows "preparing" until the article is ingested by a later run.
- Rewrite and summary payloads do not exist in the API yet; Phase 3 adds them and switches
  `generation_status` (one module) and the plain-English view (which already has the aligned layout).
- Markdown annotation bodies are shown as plain text (no Markdown renderer; HTML is never rendered).
- The Playwright smoke test needs the whole stack and is not in CI.

## Final verification

From a fresh environment (`rm -rf .venv web/node_modules web/.next` and every Python cache, then
`make setup`), with the `rb-phase45` database on port 5434 and `NEXT_TELEMETRY_DISABLED=1`:
`make check` exited 0 — ruff lint and format, docstring and lock checks, ESLint (TSDoc rules) on
the web app, mypy (strict) on backend, rbcore and tools, `tsc --noEmit` on the web app, pytest with
**411 backend**, 257 rbcore and 11 tools tests, and Vitest with **85 web tests** in 14 files. `npm
run build` then succeeded (the step CI now runs). The Playwright smoke test (6 passed) and the
Chromium screenshots were run earlier in the session against the same build, before the final
documentation commits and one layout change to the explanation cards (covered by the Vitest
tests); the fresh install removed the downloaded browser. `docker compose -p rb-phase45 down` was
run at the end; the named volume keeps the local sample corpus.

## Merge of Phase 2 fix round 2

`phase-2-corpus-licence-gate` gained fix-round-2 commits (review parts that survive text removal,
rejected XML removed from the cache, review-resolution receivers, and the retraction policy) after
this branch started; it was merged in with `git merge --no-ff`.

- **Conflicts** in `backend/README.md` (package table: kept Phase 2's `receivers` mention and this
  branch's `metadata`, `discovery` and `api` rows), `corpus/access.py` (imports: both sides' needs)
  and `tests/conftest.py` (kept both the metadata/API fixtures and Phase 2's in-memory `queue`).
- **Two `0004` corpus migrations** (`0004_review_part_survives_text_removal` and
  `0004_search_document`). They touch different tables, so a no-op merge migration
  `corpus/0005_merge_review_parts_and_search_document` joins them. Renaming this branch's
  migration was tried and rejected: a database that had already applied `0004_search_document`
  (such as the `rb-phase45` one) then fails with "relation corpus_searchdocument already exists".
- **Retraction contract.** Phase 2 made `access.retraction_notice()` the read API's way to tell a
  reader about a retraction. The paper detail's `retraction` block is now built from it
  (`api/papers.py`); the JSON shape is unchanged, so the web app's banner needs no change.
- After the merge, from a fresh `.venv` and `web/node_modules` with the `rb-phase45` database on
  port 5434: `make check` exited 0 (ruff, docstring and lock checks, ESLint, mypy, `tsc`, pytest
  with **417 backend**, 257 rbcore and 11 tools tests, Vitest with 85 web tests) and `npm run build`
  succeeded. `makemigrations --check` reports no changes, and the existing `rb-phase45` database
  migrated through the merge migration.
