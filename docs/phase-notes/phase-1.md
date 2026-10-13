# Phase 1: faithfulness benchmark scaffold, notes

Branch `phase-1-benchmark-scaffold` (from `phase-0-foundations`), built 2026-10-13 in an
unattended run. Plan.md "Phase 1" and decisions.md §1.4, minus everything that needs the owner:
no LLM calls (no API key), no raters, no final paper choice.

**Nothing in this phase is a benchmark result.** The only real outputs are the PROPOSED candidate
shortlist and a reproduction of FactPICO's published numbers (both below). Every rewrite, claim,
rating and judgement produced tonight is synthetic and labelled so.

## What was built

Package `rbbench` in `benchmark/` (Python 3.12, mypy strict, 147 tests), on top of `rbcore` for
JATS parsing, the licence gate, configuration, the LLM interface and polite HTTP.

| Step | What | Where |
|---|---|---|
| 1. Candidate shortlist | PubMed E-utilities (esearch/esummary) per slot, seeded screening order, licence checked at the PMC Cloud Service (`license_code` together with the JATS evidence, through `rbcore.licences.decide`), study type from publication types + JATS article type + a design phrase in the paper's own abstract, expert lay summary required. **24 PROPOSED candidates, 2 per slot, all 12 slots filled**; screening log of all 111 PMIDs screened. Reproducible: a rerun from the cache gave a byte-identical CSV. | `selection/`, `rbbench.selection`, `rbbench.sources` |
| 2. Ingest | JATS from the PMC Cloud Service (MD5-checked) into paragraph units `<PMCID.version>#<paragraph ID>`, gate per paper and per paragraph (`decide_part`), lay summaries kept, and a PROPOSED passage per paper (first run of rewritable Discussion paragraphs, else Results, else body; 350–650 words). All 24 candidates ingest; passages 350–639 words. | `rbbench.ingest`, `rbbench.papers` |
| 3. Rewrite harness | `rewrite_v1` prompt (paragraph-aligned, at most two `<added>`-marked sentences per paragraph); parser enforcing one rewrite per source paragraph ID and extracting additions with offsets; config matrix (temperature 0 vs default); JSONL with model, prompt version and SHA-256, temperature, timestamp, tokens, raw output; failed calls recorded as invalid cells. Fake client via `rbbench.fakes` (synthetic, labelled); real client = `rbcore.llm.AnthropicClient`, only built with `--live`. | `prompts/rewrite_v1.md`, `config/`, `rbbench.rewrite`, `rbbench.clients` |
| 4. Claim decomposition | `decompose_v1` prompt + strict JSON parser, claims linked to paragraph IDs and flagged `in_addition`; deterministic sentence fallback. | `prompts/decompose_v1.md`, `rbbench.claims`, `rbbench.sentences` |
| 5. Rubric | `rubric_v1.yaml` + `rubric_v1.md` + `rater_guide_v1.md`, all **DRAFT**: separate codes for support (supported/unsupported/contradicted), the three Peters & Chin-Yee shifts (plus derived `overgeneralisation`), lost hedge, correlation to causation, spin, substituted detail, added information (no/factual/non-factual), and per paragraph dropped limitation. Guide examples quote a CC BY fixture verbatim and label every example claim illustrative. | `rubric/`, `rbbench.rubric` |
| 6. Rater packets | Per rater: a self-contained HTML form (CSP forbids all network access, text inserted as text only, autosave, JSON export) plus the same data as JSON, in a seeded per-rater order, **blinded** (opaque unit IDs; the unblinding `key.json` stays with the coordinator). Importer validates packet, rater, rubric hash, units and labels. | `rbbench.packets` |
| 7. Agreement | Cohen's κ, Fleiss' κ, nominal Krippendorff's α, Kendall's τ-b, pooled observed agreement and prevalence per code (rated and derived); undefined values reported as undefined. Adjudication: unanimous or majority merge, disagreement CSV for the adjudicator, re-merge. Tested against published worked examples (Krippendorff 2011: 0.743 and 0.095; Wikipedia: Fleiss 0.210, Cohen 0.4, Krippendorff 0.691; SciPy docs: τ-b −0.4714), all reproduced exactly. | `rbbench.agreement` |
| 8. LLM judge | `judge_v1` prompt rendered from the rubric, strict parser, records convertible to ratings (judge-vs-human agreement reuses step 7), refuses to judge a rewrite written by its own model. FactPICO: licence checked at source, downloaded into `data/` (checksum-pinned), loader, `factpico check`, and `factpico calibrate` (judge vs expert Avg. PICO-R, τ-b). | `prompts/judge_v1.md`, `rbbench.judge` |
| 9. Baselines | AlignScore, MiniCheck (MIT checkpoints only; Bespoke-MiniCheck-7B refused), QAFactEval behind one `score(pairs)` interface, imported lazily, clear error when absent. Nothing installed or downloaded. | `rbbench.baselines`, benchmark/README.md |
| 10. Comprehension scaffold | JSON Schema, empty template, validator; FINAL requires questions and an ethics decision. No questions written. "Terms I don't know" marked as "defined by Track R (scores/)". | `comprehension/`, `rbbench.comprehension` |
| 11. Dry run | `rbbench dry-run`: fixtures → ingest → fake rewrite (both arms) → fake decomposition → packets → 3 synthetic raters → import → agreement → synthetic adjudication → fake judge → judge-vs-adjudicated agreement → `report.md`/`report.json`, headed and footed **DRY RUN — SYNTHETIC DATA — NOT RESULTS**. Deterministic. | `rbbench.dryrun`, `rbbench.synthetic` |
| CLI | `rbbench select / ingest / rewrite / decompose / packets / import-ratings / agreement / adjudicate / judge / factpico / baselines / comprehension / dry-run`. | `rbbench.cli` |

### Real findings from tonight

- **FactPICO reproduction.** Loading `all_evaluations.csv` and computing τ-b of each published
  metric against the experts' "Avg. PICO-R" reproduces the paper's instance-level table exactly:
  QAFactEval 0.289, QuestEval 0.290, AlignScore 0.244, DAE 0.152, GPT-4 0.475, Llama-2 0.055,
  Alpaca 0.081, Mistral 0.047 (n = 345). This validates the loader and the τ-b implementation on
  real data, and fixes the comparison target for our judge. (Test `test_real_factpico_...`
  runs when the data is present locally; CI skips it.)
- **The shortlist** (`benchmark/selection/candidates.csv`): 24 candidates from eLife, PLOS NTD,
  PLOS Pathogens, PLOS Biology, PLOS Genetics and PLOS Computational Biology, 2015–2022; 22 CC BY,
  2 CC0; every one passed the gate with no review flag.

## How to run

```sh
make setup && make check                 # lint, typecheck, tests (all packages)
.venv/bin/rbbench dry-run                # whole pipeline on the fixtures, SYNTHETIC
.venv/bin/rbbench --help                 # every step; see benchmark/README.md for the real-run sequence
```

## Deviations and decisions, with reasons

1. **The LLM client interface, fake and Anthropic client are rbcore's** (Phase 0), not new
   classes in rbbench. The task asks for these; they already existed with the required properties
   (lazy SDK import, key from `ANTHROPIC_API_KEY`, model from config). rbbench adds a factory with
   an explicit `--live` guard and a task-aware synthetic responder. Temperature comes from the
   matrix config. rbcore's client sends no server-side fallback (Phase 0 deviation 11), which
   matters here: a silent model switch would corrupt the benchmark's attribution.
2. **Temperature-0 arm vs current models.** Per the Claude API reference bundled with Claude
   Code (cached 2026-10-06; not verified live), a non-default `temperature` returns HTTP 400 on
   every current-generation model (Fable 5/5.1, Opus 5.5/5/4.8/4.7, Sonnet 5.5/5, Haiku 5.5);
   only Opus 4.6, Sonnet 4.6, Haiku 4.5 and older accept it. Plan.md's starting candidate
   (Sonnet 5.5) therefore cannot run the temperature-0 arm. The harness records those 400s as
   invalid cells. **Owner decision needed** (see pending).
3. **Reference-dataset membership is not verified.** The HF dataset is a ~1.6 GB Google Drive
   release behind a loading script (the HF viewer cannot serve it); downloading it was out of
   proportion for a shortlist. Candidates are instead drawn from the dataset's journals and must
   carry an expert lay summary in their JATS.
4. **Design confirmation from the abstract** was added to the classification. A first run on
   publication types alone proposed a cytokine sub-study typed as a trial and a modelling paper
   typed as a meta-analysis; trial slots now also refuse secondary/post hoc analyses.
5. **A "rewrite" is a passage, not a paper.** §1.4 wants 12 rewrites of about 20–30 claims each,
   so each paper contributes one passage of 350–650 words, proposed by a fixed rule (Discussion
   first, because hedges and limitations concentrate there) and recorded as PROPOSED.
6. **Rubric shape choices** (all in the DRAFT for review): `support` and `added_information` are
   three-valued nominal codes; `added_information` applies to every claim, marked or not, so
   unmarked additions are caught; `dropped_limitation` is rated per paragraph because an omission
   belongs to no single claim; `overgeneralisation` is derived (any of the three shifts), never
   rated directly; "substituted number or population" is named `substituted_detail` and also
   covers intervention, comparator and outcome (PICO).
7. **The rewrite prompt states operational rules** (keep quantifiers, tense, hedges, numbers,
   limitations; no causal words unless the source uses them) and **avoids "be accurate"**, which
   Peters & Chin-Yee found increased overgeneralisation. Whether these rules themselves change
   behaviour is a question for a later prompt version.
8. **Packets are blinded**, beyond the spec: raters never see arm, model or rewrite IDs.
9. **No third-party code was copied.** Reuse was considered for each part: `krippendorff` is
   GPL-3.0 (not allowed); pysbd (MIT) fails under Python 3.12 warnings-as-errors and is stale;
   statsmodels/scipy are permissive but heavy for four formulas, and the task asked for
   implementations tested against published examples; FactPICO's MIT code was not needed (only its
   CC BY 4.0 data). The baselines are wrapped, not vendored. All recorded in the licence inventory.
10. **LLM decomposition never silently falls back** to sentences; the method is recorded on each
    claim, and a failed parse is an error.
11. **FactPICO calibration aggregation:** each summary is split into sentences, each judged against
    the abstract, and the summary score is the share judged `supported`. FactPICO's experts rate
    PICO elements, so the τ-b, not the scale, is the comparable figure. A better aggregation may
    replace this once real judge output exists.
12. **The dry run uses the Phase 0 fixtures in place** (`libs/rbcore/tests/fixtures/jats/`), with
    their manifest's recorded licence evidence, instead of committing copies.
13. **No Docker/Postgres was used.** Nothing in Phase 1 needs a database; no containers were
    started.

## Pending the owner

1. **API key and models.** Put `ANTHROPIC_API_KEY`, `RB_LLM_GENERATION_MODEL` and a *different*
   `RB_LLM_JUDGE_MODEL` in a local `.env`. Decide the temperature arm (deviation 2): use a
   4.6-generation generator for that comparison, or replace the arm (for example an effort-level
   arm, in a new `rewrite_matrix_v2.yaml`).
2. **Approve the 12 papers**: one option per slot in `benchmark/selection/candidates.csv`. Worth a
   second look before approving: **S03 A** (placebo response across trials) and **S03 B** (by its
   title, a correlational analysis set in the Rakai male-circumcision trial) use trial data but are not primary trial reports;
   **S06 A** (phylodynamic modelling) is typed observational/cohort; **S12 B** (dosing model) is a
   pharmacometric meta-analysis. Then approve or edit the proposed passages
   (`rbbench ingest --only S01A,...` writes `passages.jsonl`).
3. **Review the DRAFT rubric and rater guide** (`benchmark/rubric/`), including the three open
   questions at the end of `rubric_v1.md`.
4. **Recruit at least two domain-literate raters**; give them pseudonymous IDs for the packets.
5. **Write the human arm**: plain-language versions of the same passages, by a person.
6. **Write the comprehension questions** (template in `benchmark/comprehension/`).
7. **Research ethics:** check whether **University of Alberta** research-ethics approval is
   needed before recruiting lay readers (and raters), and record it in the question set's
   `study.ethics`; the schema will not accept a FINAL set without it.
8. **Optional baselines:** install in a separate environment (benchmark/README.md); verify the
   QAFactEval model licences first; record versions in the licence inventory.
9. After the run: record the chosen model, settings, prompt and the gate threshold in
   decisions.md (Plan.md "Decisions this plan will produce").

## Known limitations

- Classification is metadata-based (publication types, JATS type, a design phrase in the
  abstract); nobody has read the papers. See pending item 2.
- The sentence splitter is rule-based (abbreviations, initials, brackets); odd punctuation can
  split or join sentences wrongly. It is only the fallback decomposition.
- Passage proposal is a heuristic; a Discussion opening can be mostly summary rather than claims.
- The packet form was exercised under Node with a DOM stub (all questions render, answering
  everything completes it, export succeeds) but not in a real browser: headless Brave hung on
  this machine. Open one packet in a browser before sending it to raters.
- Saved answers live in the rater's browser storage for that file; a rater who clears site data
  before exporting loses them (the export is the record).
- No cost tracking or budget for live runs beyond recording token counts per call.
- Rate limiting is per process; do not run two `rbbench select` processes at once.
- The dry run's numbers come from synthetic raters with chosen change rates and a fake judge;
  they demonstrate the plumbing only.
