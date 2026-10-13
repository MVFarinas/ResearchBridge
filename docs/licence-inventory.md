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
| spaCy | MIT | — | 3.8.16 | dependency (rbscores) | Tokenising, tagging, lemmatising and dependency parsing for both scores (Track R). Pulls in thinc, srsly, cymem, preshed, murmurhash, catalogue, confection, wasabi, weasel, spacy-legacy, spacy-loggers (MIT), blis (BSD-3), numpy (BSD-3 plus bundled permissive parts), typer, rich, cloudpathlib, smart-open (MIT), requests (Apache-2.0), jinja2 and markupsafe (BSD-3), tqdm (MPL-2.0 AND MIT, used unmodified), shellingham (ISC). |
| en_core_web_sm (spaCy English pipeline) | MIT | **Weights MIT** (model card `license: MIT`); trained by Explosion on OntoNotes 5, which Explosion licenses commercially from the LDC, plus WordNet 3.0 (WordNet licence, permissive) | 3.8.0 (wheel URL pinned in `scores/pyproject.toml` and the lock; wheel SHA-256 `1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85`, as recorded by pip in the installed `direct_url.json`) | dependency (rbscores), installed into `.venv` from the spaCy GitHub release, never committed | Default pipeline (`RB_SCORES_SPACY_MODEL` overrides it). Named-entity recogniser excluded at load. |
| wordfreq | Apache-2.0 (verified in the installed `LICENSE.txt`) | **Data CC BY-SA 4.0**, with source terms: Google Books Ngrams (free use, attribution appreciated), Wikipedia, Leeds Internet Corpus, ParaCrawl (CC licences), OpenSubtitles 2018 (attribution), SUBTLEX (free for any use with credit to Brysbaert et al.), Twitter statistics only | 3.1.1 | dependency (rbscores) | Word familiarity (Zipf frequency) for jargon density and burden weights. See the note below. Pulls in ftfy, msgpack, regex (Apache-2.0; regex also CNRI-Python), langcodes (MIT) and locate (MIT `LICENSE` file, although its PyPI classifier says "Other/Proprietary"). |

Transitive Python dependencies are pinned in [requirements/dev.txt](../requirements/dev.txt).
Transitive dependencies under weak, file-level copyleft (MPL-2.0, e.g. certifi 2026.7.22 via
httpx and pathspec 1.1.1 via mypy) are acceptable when installed and used unmodified; never copy
or modify their source. The permissive-only rule above still applies to every direct dependency
and to all copied code.

**wordfreq data (CC BY-SA 4.0): why it is acceptable, and the obligations (Track R, 2026-10-13).**
Share-alike is not on the forbidden list (no non-commercial or no-derivatives terms), and we use
the data only by looking up frequencies in the unmodified, separately installed package. Scores
computed from those lookups are our own outputs, not adaptations of the word lists. Obligations
if this changes: (1) any word list or frequency table we *derive* from wordfreq and ship (for
example a cached familiarity table in the product) must be released under CC BY-SA 4.0 with
attribution to wordfreq and its sources, including the credit to the SUBTLEX authors; (2) keep
wordfreq's attribution in the product's credits when the scores are displayed. Alternatives
considered: SUBTLEX-US alone (redistributed inside wordfreq under the same conditions; smaller
and subtitle-only), Google Books Ngrams (permissive terms but very large and book-skewed), the
De-Jargonizer's BBC counts (not available under any licence), and Norvig's web counts (derived
from the LDC Web 1T corpus, whose terms are unclear). wordfreq's data is frozen: its author
stopped updating it in 2024 (`SUNSET.md`), so newer terms look rarer than they are.

### Evaluated and not used

| Project | Code licence | Version reviewed | Decision |
|---|---|---|---|
| scispaCy biomedical pipelines (`en_core_sci_sm`) | Apache-2.0 (library) | 0.5.4 model (`meta.json` read from the release archive) | **Not used** (Track R). The model weights are **CC BY-SA 3.0** (not forbidden, but share-alike adds obligations) and require spaCy `>=3.7.4,<3.8`, which conflicts with spaCy 3.8 in the lock; the models are distributed as S3 tarballs, not wheels. Revisit if biomedical parsing quality becomes the bottleneck; the pipeline name is configurable (`RB_SCORES_SPACY_MODEL`). |
| ScholarPhi (allenai/scholarphi) | Apache-2.0 | `main` (last commit 2023-03-29), reviewed for design only | **Not used** (Track R). Its definition detection is a neural pipeline over LaTeX sources with a PostgreSQL backend; our input is JATS and plain text. Definitions are detected with Schwartz-Hearst plus definitional patterns written for this project. No code was copied. |
| pubmed_parser | MIT | 0.5.1 (PyPI sdist) | **Not used** for `rbcore.jats` (Phase 0). It parses with lxml's default parser (no hardening against entities or network), uses bare `except` and `print`, flattens only one level of inline markup, returns flat paragraphs with no stable IDs or nested sections, and does not record which field a licence came from. Its approach to matching COI footnotes by attribute value informed ours; no code was copied. |

## 2. Planned: permissive, attribution only

| Project | Kind | Code licence | Weights / data licence | Version pinned | How used | Notes |
|---|---|---|---|---|---|---|
| allofplos | PLOS bulk download | MIT | PLOS content CC BY | — | planned (Phase 2) | |
| LaTeXML | arXiv LaTeX to HTML | Public domain | — | — | planned (after MVP) | |
| ar5iv | arXiv HTML | MIT | per-paper licence | — | planned (after MVP) | |
| GROBID | PDF fallback | Apache-2.0 | — | — | planned | |
| Docling | PDF fallback (§1.2 uploads) | MIT | models Apache-2.0 (Heron, Granite-Docling) | — | planned (Phase 6) | |
| olmOCR | PDF fallback | Apache-2.0 | Apache-2.0 | — | planned | |
| @recogito/text-annotator (+ pdf-annotator) | Passage anchoring | BSD-3-Clause | — | — | planned (Phase 4) | v4.3.7 at report time. |
| pdf.js | PDF rendering | Apache-2.0 | — | — | planned (Phase 6) | |
| Hypothesis client (anchoring modules) | Anchoring | BSD-2-Clause + MIT subcomponent | — | — | planned, **pending review** (§4) | |
| Hypothesis h | Annotation server | BSD-2-Clause | — | — | reference for moderation design | Not self-hosted (§1.6). |
| PaperQA2 (paper-qa) | Cited extraction (F3) | Apache-2.0 | — | — | planned (Phase 3) | |
| Kotaemon | Grounded QA | Apache-2.0 | — | — | reference | |
| open-notebook | Grounded QA | MIT | — | — | reference | |
| pyalex | OpenAlex client | MIT | OpenAlex data CC0 | — | planned (Phase 4) | |
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
| PersonalizedJargon | Jargon familiarity | Apache-2.0 | — | — | planned (Track R, second half) | Not used in the first half: a reader-profile adjustment needs the human data first. |
| definition-complexity | Definitions | Apache-2.0 | — | — | planned (Track R, second half) | Not used yet; relevant to how well a definition explains, not whether one exists. |

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
| PMC Cloud Service (`s3://pmc-oa-opendata`) | Per-article licence (`license_code`); bucket terms | planned (Phase 2); fixtures (Phase 0) | Acknowledge NLM; no PMC logo or implied endorsement; redistribute only licensed data; keep it current or say it is not; honour `is_retracted`. `TDM` = never ingest. |
| Europe PMC REST | Per-article licence; free API | fixtures (Phase 0); planned | Its `fullTextXML` copy can lack the machine-readable licence that PMC's copy has (see fixtures); prefer the PMC copy. |
| PLOS (journals.plos.org, allofplos) | CC BY 4.0 (some CC0) | fixture (Phase 0); planned | Attribution. |
| arXiv OAI-PMH and API | Metadata CC0; per-paper licence; API ToU | planned (after MVP) | At most 1 request per 3 s. Non-exclusive licence = no display. |
| bioRxiv / medRxiv API | Per-preprint licence | planned | `cc_no` = never ingest. |
| NCBI E-utilities | NLM terms | planned | At most 3 requests/s without a key (10 with `NCBI_API_KEY`). |
| OpenAlex | CC0 | planned (Phases 4-5) | Usage-based pricing since Feb 2026; cache; show "as of" dates. |
| OpenCitations | CC0 | planned | |
| NIH iCite | Public domain | planned | |
| Crossref (incl. Retraction Watch data) | Metadata open; Retraction Watch citation requested | planned | Cite Retraction Watch. Licence fields are secondary signals only. |
| DOAJ | CC0 metadata | planned (discovery only) | Licence is journal-level, never the gate. |
| PLOS and eLife lay-summary datasets (Goldsack et al. 2022: HF `tomasg25/scientific_lay_summarisation`, and the same splits as `BioLaySumm/BioLaySumm2025-eLife` / `-PLOS`) | CC BY 4.0 (tomasg25 card; PLOS and eLife articles are CC BY 4.0 at the publishers). The authors' GitHub repository has no licence file; the BioLaySumm 2025 cards state none. | **used** (Track R validation 1: validation splits, 241 eLife + 1,376 PLOS pairs; 100 training articles each for calibration); planned (Phase 1) | Downloaded to `data/` only, never committed; attribute the authors and the CC BY sources. Re-check each paper's licence at its primary source before display or rewriting. |
| Hugging Face dataset viewer API (`datasets-server.huggingface.co/rows`) and Hub API | Free public API; Hugging Face terms of service | service (Track R validation 1 download) | Unauthenticated, at most 1 request per second through `PoliteFetcher`, cached under `data/`. |
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
| MedReadMe | data | none | Ask the authors before any use (pending the owner; not used by Track R). |
| De-Jargonizer | code | none | **Reimplemented** from the published method only (Rakedzon et al. 2017, PLOS ONE, CC BY): `rbscores.familiarity.jargon_band` and the jargon-density formula. Its code was not read or copied, and its BBC word counts are not used (wordfreq frequencies instead). |
| Cochrane and SciNews texts | data | third-party copyright despite CC BY tags | |
