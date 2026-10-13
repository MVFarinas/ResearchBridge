# Decisions — ResearchBridge

Locked scope and architecture choices, and the questions still genuinely open. When this file
conflicts with [inspiration.md](inspiration.md), **this file wins** — inspiration.md is the
original brain-dump and is kept as background, not as spec.

Format: numbered, dated, with the alternatives considered. A decision that invalidates an earlier
one supersedes it in writing rather than editing it away.

Supporting evidence for the 2026-10-13 decisions (prior art, licences of reusable code, datasets,
metrics) is in [reports/Prior art and reusable open source.md](reports/Prior%20art%20and%20reusable%20open%20source.md).

---

## 1. Locked

### 1.1 Licence-gated corpus — the keystone safety decision (2026-08-10)

**Only ingest papers whose licence permits what we do to them, and store the licence per paper.**

Every core feature is reproduction. The rewriting feature produces a **derivative work** of the
full paper; the inline-explanation feature **displays the original in full**. Only the summary
engine is comfortably safe, since facts are not copyrightable. Feature 2 is the exposed one, and
it is also the one the project treats as most important, because it is what preserves scientific
integrity.

**"Open access" is not one thing, and this is the part that bites.** CC-BY permits derivative
works with attribution. **CC-BY-ND explicitly forbids them**, and a plain-English rewrite is
squarely a derivative. So the rule is not "open access only":

| Licence | Display original | Rewrite (derivative) |
|---|---|---|
| CC-BY, CC-BY-SA | yes | yes, with attribution |
| CC-BY-ND | yes | **no** |
| CC-BY-NC variants | yes | yes, but constrains commercialisation later |
| All rights reserved / paywalled | **no** | **no** |

**Decision:** store a `licence` field per paper at ingestion and gate features on it. Rewriting
requires derivative permission. Never ingest paywalled or all-rights-reserved content.

**Why this is not a painful compromise.** arXiv, PubMed Central, PLOS and DOAJ are millions of
papers, most under CC-BY. The audience named in inspiration.md — general public, students,
journalists, people checking a claim they saw online — largely cannot reach paywalled papers
anyway, so the excluded corpus is one they could not use. And the rule is *checkable*: a licence
field either grants derivative rights or it does not, with no per-paper judgement call.

**Consequences.** The ingestion schema needs the licence field from day one; retrofitting it once
a corpus exists means re-deriving provenance for everything already stored. Attribution and licence
display become UI requirements, not nice-to-haves. If a paid tier is ever considered, the NC
variants have to be re-examined, because non-commercial terms and a subscription do not mix.

**Alternatives rejected:** ingest anything and rely on fair use or fair dealing (unpredictable
across jurisdictions, and weakest for exactly the full-text-display case we need); link out to the
publisher rather than display (kills feature 2, which is the differentiator); ask publishers for
permission (does not scale for a solo project, and blocks the build on other people's legal teams).

**Addendum (2026-10-13) — licence granularity and sources.** Research since this decision
sharpened two points without changing it:

- **Licences can be finer than per paper.** In JATS XML a figure or table can carry its own
  `<permissions>` block, so store a licence per figure/table where one is given, and fall back to
  the article licence otherwise. Display and rewrite gating applies at that level.
- **Where the licence comes from, per source.** PMC: the `license_code` in the per-article JSON of
  the `pmc-oa-opendata` S3 bucket (PMC retired its FTP service and OA file lists in Aug 2026;
  `TDM` = author manuscript, never ingest). arXiv: the `<license>` URI from OAI-PMH
  (`metadataPrefix=arXiv`); the search API has no licence field, and most arXiv papers carry the
  non-exclusive distribution licence, which does **not** permit display or derivatives. PLOS:
  CC-BY/CC0 throughout. DOAJ: licence is journal-level only, so DOAJ is a discovery source, not
  a licence source. OpenAlex/Unpaywall/Crossref licence fields are secondary signals only, never
  the gate. Free-text `<license-p>` prose is for display, never for automated decisions.
- **The table above is missing a row.** CC-BY-NC-ND is display-only (no derivatives, no
  commercial use), and it is the largest non-commercial category in PMC (~1.1M full-text papers).
  Treat it as the CC-BY-ND row plus the NC caveat.
- **Share-alike sets the output's licence.** A rewrite of a CC-BY-SA paper must itself be released
  under CC-BY-SA, so the licence field determines the licence of what we publish, not only whether
  we may rewrite.
- **"Most under CC-BY" holds for PMC and PLOS, not arXiv.** Europe PMC has ~5.4M rewrite-eligible
  full-text papers (CC-BY, CC-BY-SA, CC0); only ~10–15% of arXiv (~216k–304k papers) carries a
  licence that permits display at all. The corpus will be predominantly biomedical and life
  science at launch, whether or not that was the intent.

Scope note: §1.1 governs the **shared corpus**. Files a user brings themselves are governed by
§1.2, which narrows rather than replaces this decision.

### 1.2 Private bring-your-own-PDF mode (2026-10-13)

**A user may upload a paper they already have, including a paywalled one, and get explanations
for themselves only. Nothing from it enters the shared corpus or is shown to anyone else.**

The lookup flow in §1.5 ("does an annotation already exist for this DOI?") is safe for corpus
papers and unsafe for everything else: annotations embed quotes of the passages they anchor to, so
caching and re-serving an LLM annotation of a paywalled paper redistributes a derivative of
copyrighted text. Private, per-user processing is a different posture from public display — the
same posture as reading a PDF you own with a dictionary open.

**Decision:**

- Uploaded files are parsed and explained for the uploading user only. They are stored, if at all,
  in that user's private library, deletable by them, and never indexed for search.
- Explanations generated from an upload are **never** written to the shared annotation store and
  never served to another user, even for the same DOI.
- If the uploaded paper turns out to be in the corpus (licence permits), the user is redirected to
  the shared version instead.
- The LLM provider is used with no-training / minimal-retention settings for uploaded content.
- Every output in this mode carries the accuracy disclaimer from §1.3.

**Before launch:** obtain a legal opinion on this mode (fair dealing for research and private
study is the relevant Canadian concept, but this needs a lawyer, not a design doc). Until then the
mode can be built but not opened to the public.

**Longer-term path for paywalled papers:** a browser extension that overlays annotations on the
copy the reader is already legitimately viewing (the Hypothesis model), so nothing but short
anchors and the explanations themselves is stored. Not in scope yet.

**Alternatives rejected:** treat uploads as corpus ingestion (directly violates §1.1); share
annotations of uploaded paywalled papers between users who each hold a copy (attractive, but it
is exactly the redistribution question the legal opinion has to answer first — revisit after it);
drop uploads entirely (loses the "paper I was sent is paywalled" use case, which is real for the
target audience).

### 1.3 Annotation model — phased hybrid, LLM drafts as the seed (2026-10-13)

*Resolves §2.1.*

**Phase 1 ships LLM annotations so every corpus paper is explained on day one. Phase 2 adds a
community that verifies, corrects and supersedes those annotations passage by passage. The
human-verified layer is the moat.**

§2.1's objection was that a hybrid inherits both cost structures. Phasing defuses that in time:
phase 1 carries only model cost; moderation cost arrives only once there is a community to moderate.

**How phase 2 works — LLM output is a draft, not a placeholder to retire:**

- Readers can **verify, correct, or vote on** an existing LLM annotation, as well as write their
  own. Fixing a draft is a far lower bar than writing from blank, which is the best available
  answer to the cold-start problem. If polished LLM notes simply covered everything and waited to
  be replaced, there would be no gap for a community to fill.
- Supersession is **per annotation / per passage**, never per paper. Most papers will be mixed
  for years. "LLM-based annotations" is therefore a **provenance filter** in the reader (show
  human / show LLM / show both), not a separate per-paper view.
- When a human-verified or human-written annotation exists for a passage, it is shown by default;
  the LLM draft stays available behind the filter, not deleted.

**Data model, from day one** (the §1.1 lesson again — provenance is painful to retrofit):

- Annotations are stored as W3C Web Annotation-style records (TextQuote + TextPosition selectors)
  in our own database.
- Each has a `provenance`: `llm`, `human`, or `llm_edited`; plus `model`, `prompt_version`, and a
  full edit history. Votes, reports and revisions are separate tables.
- Every LLM-originated annotation shows an accuracy disclaimer until a human has verified it.

**Why this is evidence-backed, not just a moat story.** LLM "highlight and explain" is now a
commodity (Explainpaper, SciSpace, alphaXiv all offer it to researchers); none offers a
human-verified layer for lay readers. And in a 2025 study with 150 lay readers (Guo et al.),
human-written summaries produced significantly better comprehension than LLM ones even though
readers *rated* them similarly — so the community layer should be genuinely better, not only
harder to copy.

**Alternatives rejected:** community-only (empty product on day one); LLM-only (no moat, and its
quality ceiling is the model's); coexisting as independent parallel systems (inherits both cost
structures at once with no path between them — the version §2.1 warned about).

### 1.4 Faithfulness benchmark — 12 rewrites, scored claim by claim (2026-10-13)

*Resolves §2.2.* **This is the first piece of work, before product code.**

**Size and unit.** About **12 rewrites**, each decomposed into its individual claims, giving
roughly 250–350 claim-level judgements. Twelve holistic ratings would be too few to measure
inter-rater agreement; a few hundred binary claim judgements is enough. Narrow yes/no checks also
agree far better than an overall faithfulness rating (κ 0.79–0.95 in Peters & Chin-Yee 2025 vs
Krippendorff's α 0.20–0.64 for holistic crowd ratings in Devaraj 2022).

**Selection — biomedical first.** All 12 come from biomedicine and the life sciences, spread
across study types (randomised trials, observational studies, lab/mechanistic work, reviews).
That is where the licence-gated corpus mostly lies (§1.1 addendum) and where the open evaluation
data is: the PLOS and eLife lay-summary datasets (CC-BY; each paper has an expert lay summary to
compare against), PLABA (CC0, biomedical abstracts with plain-language adaptations), and FactPICO
(CC BY 4.0, expert-rated LLM lay summaries of trials, for calibrating the judge). Other fields
get their own round once the corpus extends to them. All selected papers must pass §1.1.

**Rubric, per claim:**

- Supported / unsupported / contradicted by the source passage.
- Plus checks targeted at the known failure modes: **overgeneralisation** of findings, **dropped
  hedges or limitations**, and **causal inflation** (correlation reworded as causation).

**Raters.** At least two domain-literate raters per rewrite; disagreements adjudicated and
agreement reported. Lay raters are for comprehension, not faithfulness.

**Arms.**

1. LLM rewrite(s) — the candidate model(s) and prompts.
2. **A human-written arm** for the same passages. No published study compares community-written
   explanations of scientific passages with LLM ones; this is the comparison §1.3's phase 2 rests on.
3. **An LLM judge scored against the human raters,** to decide whether faithfulness can be
   checked automatically in production. Prior automatic metrics correlate poorly with experts on
   this kind of text (Kendall τ ≈ 0.24–0.29 for AlignScore/QAFactEval on FactPICO; ≈ 0.48 for a
   GPT-4 judge). The judge should not be the same model that generated the rewrite.

**Outputs.** The generation model and settings are chosen by this benchmark, not in advance.
Reported in prior work and worth testing: temperature 0 cut overgeneralisation odds by ~76%, and
prompting the model to "be accurate" *increased* overgeneralisation.

**Alternatives rejected:** a few dozen holistic passage ratings (the original §2.2 sketch — more
rater time for weaker statistics); automatic metrics only (they miss inserted and substituted
facts, which is the failure that matters most here); spreading the 12 across all fields (the
first draft of this decision — too few rewrites per field to say anything about any of them, and
most fields would have no reference data or corpus behind them).

### 1.5 Form factor and entry points (2026-10-13)

*Supersedes the form-factor part of §3.*

**Responsive web app first. Browser extension later (see §1.2). No native app.** Long-form
reading suits the web, and public, indexable plain-English pages are the main acquisition
channel: someone searches a paper's title and lands on the readable version.

**Entry point 1 — search (Google Scholar-like).**

- Search covers **all scholarly metadata** via OpenAlex (CC0), so it feels like Scholar, not just
  the licensed corpus. Keyword search, filters, sort by date.
- Each result is tagged by what we can offer: **plain-English available** (corpus, derivative
  permitted), **original + annotations only** (corpus, e.g. CC-BY-ND), or **original elsewhere —
  bring your own PDF** (§1.2).
- A corpus paper opens on the plain-English rewrite, with a toggle to the original-plus-annotations
  view (feature 2).
- **"Read original paper" links to the DOI** (`https://doi.org/…`, the publisher's canonical
  version). A secondary "Find on Google Scholar" link is a Scholar *search URL* for the title/DOI.
  Linking is fine; scraping or querying Scholar programmatically is not (no API; robots.txt
  disallows it).

**Entry point 2 — paper lookup.**

- The user enters a DOI, title, author, or arXiv/PMC ID. If the paper is in the corpus, they get
  the shared version with its existing annotations.
- If it is licence-eligible but not yet ingested, it is ingested and LLM-annotated on demand,
  then cached for everyone (with the §1.3 disclaimer).
- If it is not licence-eligible, the user is offered §1.2's private upload mode.

### 1.6 Stack and hosting (2026-10-13)

*Supersedes the stack and hosting parts of §3.*

| Layer | Choice | Why |
|---|---|---|
| Frontend | **Next.js** (React, TypeScript) | Server rendering for indexable paper pages. `@recogito/text-annotator` (BSD-3, maintained, React wrapper) for passage anchoring on HTML; pdf.js (Apache-2.0) for §1.2 uploads. |
| Backend | **Django** (Python) | Ingestion, parsing, LLM and scoring work is Python regardless. Django admin is a free moderation console. ResearchHub's backend (Django, MIT) is the best code to borrow for votes, reputation and discussion. |
| Database | **Postgres + pgvector** | Papers (licence per paper and per figure), annotations with provenance (§1.3), discussion. Postgres full-text search for the corpus until it is outgrown. |
| Background jobs | Worker process on the same codebase | Ingestion and LLM generation are long-running and must not run in request handlers. |
| Ingestion | PMC S3 JATS XML; arXiv OAI-PMH licence + native arXiv HTML (LaTeXML); PLOS JATS; **Docling** only when a PDF is unavoidable | Structured text beats PDF parsing for anchoring. Docling is MIT with Apache-2.0 models. Avoid Marker/Surya, MinerU and Nougat — their model-weight licences restrict commercial use. |
| Metadata and metrics | OpenAlex, OpenCitations, NIH iCite, Crossref (incl. Retraction Watch data) | CC0 / public domain / open. **Not** Semantic Scholar's API: its licence forbids embedding it in a commercial product. |
| LLM | **Claude API** — Sonnet 5.5 as the starting candidate for bulk rewriting and annotation; final choice by §1.4 | Lowest overgeneralisation rates among models tested in Peters & Chin-Yee 2025 (≈0–20%). Model IDs live in config, not code. |
| Auth | Email + **ORCID** sign-in | ORCID makes a verified-researcher badge on community annotations nearly free. |
| Hosting | **One managed platform** (Render or Railway) for web, worker and Postgres; **Cloudflare R2** for files | Fewest moving parts for a solo project; R2 has no egress fees. Revisit when cost or scale says so. |

**Licence rule for reused code:** prefer permissive (MIT, BSD, Apache-2.0). **AGPL** code (e.g.
Open Paper, PDFMathTranslate, ODDPub) is reference-only — copying it into a hosted product forces
open-sourcing ours. GPL tools (statcheck, rtransparent) may run offline as validators, not ship
inside the product. Check model-weight licences separately from code licences.

**Alternatives rejected:** all-TypeScript backend (fights the Python-only ingestion and NLP
ecosystem); self-hosting Hypothesis as the annotation backend (BSD-2 and very capable, but needs
Elasticsearch and RabbitMQ, has no voting/reputation, and is not officially supported for
self-hosting — kept as a source of anchoring code to borrow); native mobile app first (wrong form
factor for reading papers, and no search-engine discovery).

---

## 2. Open — need a decision before build

### 2.1 Annotation model ⚠️ this one decides what company this is

> **Resolved 2026-10-13 → §1.3** (phased hybrid; LLM drafts seed a community layer). The original
> framing is kept below for the record.

How do readers get explanations of difficult passages? inspiration.md offers two and says they
"may coexist."

- **(a) Community annotation**, Genius-style. Humans explain passages for each other.
- **(b) LLM annotation.** Generated explanations, no community required.

These are **different products with different cost structures**, not a feature toggle. (a) means
cold-start problems, moderation, and network effects, with a quality ceiling set by the crowd; it
is defensible once it works because the annotations are a moat. (b) ships alone on day one with a
quality ceiling set by the model, and inherits every faithfulness risk in §2.2; it is also
trivially copyable.

A hybrid inherits **both** cost structures, so "they may coexist" is the option needing the most
scrutiny, not the safe middle. **Pending.**

### 2.2 Faithfulness measurement — how do we know a rewrite is honest?

> **Resolved 2026-10-13 → §1.4** (12 rewrites, claim-level scoring, human and LLM-judge arms).
> The original framing is kept below for the record.

The stated design philosophy is to preserve scientific integrity and never turn nuance into
clickbait. That is not a philosophy question, it is a **measurable** one: a rewrite that introduces
a claim the source does not support is a grounding failure.

This is the same problem, and the same metric, as the Groundedness scoring in
[the JAMN Bot study](https://github.com/JAMNSoftware/jamn-rag-benchmark) — score generated text
against the source passage on a rubric, with human raters setting the reference and inter-rater
agreement establishing credibility. A small benchmark of a few dozen passages would de-risk the
core feature before any product work, and would settle §2.1 with evidence rather than preference.

**Pending** — but this is the cheapest high-value thing available and should probably come first.

### 2.3 Credibility scoring is a claim about other people's work

inspiration.md proposes journal-quality signals, including distinguishing respected journals from
predatory ones. Publishing a low-quality label about a named journal in a shipped product is a
materially different risk surface from summarizing a paper. Options: use only neutral quantitative
signals (citation count, recency), defer to an external list and attribute it, or drop the feature.

**Deferred (2026-10-13).** The intent behind it stands: a finding in Nature and one in a small
university journal should not look equally weighty. But the journal-level question is not needed
to ship.

- **Can ship without resolving this:** paper-level, neutral signals — citation count and growth
  over time, field-normalised citation percentile, recency, and retraction / expression-of-concern
  status. All from CC0, public-domain or open sources (OpenAlex, iCite, Crossref's Retraction Watch
  data).
- **Trigger to decide:** before the product shows **any signal about a journal** rather than a paper.
- **Why it will come back hard:** the licence-gated corpus mostly excludes Nature itself and leans
  towards PLOS, Nature Communications, Scientific Reports, MDPI, Frontiers and small DOAJ journals —
  exactly the publishers whose standing is most disputed (e.g. Finland's JUFO downgraded 271 MDPI and
  Frontiers journals for 2025, with public objection). If decided later, the research favours
  attributed, positive list membership ("Listed in DOAJ / MEDLINE") and field-normalised citedness
  over any negative verdict, and never treating absence from a list as a verdict.

### 2.4 The two invented metrics need definitions before they need code

The **readability/convolution score** and the **prior-knowledge burden score** are the original
contributions in inspiration.md, and both are currently vibes. Either could be a small publishable
result on its own. Neither can be built until it is defined and validated against human judgement.

**In progress — draft definitions (2026-10-13).** Still pending validation.

The two scores measure **different things** and must stay separable: readability is *how it is
written*; burden is *what it assumes*. A paper can be clearly written but assume a great deal
(dense mathematics), or convoluted but assume little.

**Readability / convolution score — how hard the prose itself is.**

- Components: sentence length; syntactic depth (how deeply clauses nest); nominalisation density
  ("utilisation of" for "using"); passive-voice rate; jargon density.
- Rationale: reading-grade formulas alone track perceived difficulty of health text poorly; adding
  a jargon count improves them (MedReadMe).
- Validation: (1) free pairwise data — PLOS and eLife pair each paper with an expert lay summary,
  so the score should rank the lay version easier in nearly every pair; (2) agreement with lay
  readers' pairwise "which is harder?" judgements on a held-out sample.

**Prior-knowledge burden score — how much the reader must bring that the paper does not supply.**

- Extract technical terms and the external results the text leans on ("as shown in [12]").
- Remove those the paper itself defines.
- Weight each remaining item by how unfamiliar it is likely to be — e.g. its rarity in general text.
- Burden = weighted total per 1,000 words.
- Validation: lay readers mark the terms they do not know in sample passages; the score should
  track what they mark. Personalised-jargon work (August et al.) found familiarity varies a lot even
  within one subfield, so report it as a population estimate, not a per-reader truth.

**Shared pipeline with feature 2.** The burden score's output — undefined, unfamiliar terms — is
the priority list for which passages get annotated (§1.3). Build the term extraction once.

**Reuse with §1.4.** Use the same raters and passages where possible; comprehension-oriented lay
raters suit these scores better than faithfulness checks.

---

## 3. Not decided, not yet needed

> **Superseded 2026-10-13 → §1.5 (form factor) and §1.6 (stack and hosting).** Original text:

Stack, hosting, and form factor are untouched. There is no code yet and nothing here constrains
them, except that §1.1 requires a licence field wherever papers are stored.
