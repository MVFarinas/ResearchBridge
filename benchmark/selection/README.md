# Candidate shortlist: PROPOSED, awaiting the owner's approval

**Nothing here is final.** `candidates.csv` proposes **24 candidates, two per slot** (options A
and B). The owner picks one per slot to make the 12 benchmark papers (decisions.md §1.4), or
rejects a slot and asks for another draw. Until then the `status` column says `PROPOSED`.

## Files

| File | What |
|---|---|
| [slots_v1.yaml](slots_v1.yaml) | The selection config: journals, study-type filters, years, seed, 12 slots |
| [candidates.csv](candidates.csv) | The proposal, one row per candidate, with licence evidence |
| [screening_log.csv](screening_log.csv) | Every PMID screened, accepted or rejected, with the reason |
| [pool_log.csv](pool_log.csv) | Per slot: the esearch query, PubMed's total hit count, PMIDs retrieved, whether that was truncated, and how many were eligible for screening |

Regenerate with `rbbench select` (network: about 600 polite requests on a cold cache, a few
minutes; instant from the cache in `data/benchmark/cache`).

## Method

**Source.** The reference datasets are the PLOS and eLife lay-summary corpora (Goldsack et al.,
EMNLP 2022; HF `tomasg25/scientific_lay_summarisation`, CC BY 4.0). Their journals are eLife and
five PLOS journals (Biology, Computational Biology, Genetics, Pathogens, Neglected Tropical
Diseases); candidates are drawn from those journals, published 2015–2022, and **must carry an
expert lay summary** in their JATS (eLife digest or PLOS author summary), which is what places a
paper in that dataset family and gives a human-written plain-language reference.

**Twelve slots, three per study type** (randomised trial, observational, lab/mechanistic,
review), spread across eLife and the PLOS journals (see `slots_v1.yaml`).

**For each slot:** PubMed E-utilities `esearch` with the slot's journals, the study type's
filter (PubMed publication types; for lab/mechanistic, a MeSH filter for animal or cell studies
without human subjects), the year range and the PMC subset; then the PMIDs are put in a
**seeded order** (SHA-256 of `seed:PMID`) and screened one by one until two pass. One esearch
call returns at most 500 PMIDs, in E-utilities' default order (no `sort` is sent). Where a query
has more hits than that (S07, S08, S09, S11 and S12; see `pool_log.csv` for the counts), the
pool is **PubMed's first 500 by its default order**, and the seeded order only permutes those:
it removes PubMed's ordering within the pool, not PubMed's choice of which 500 to return.
Screening, cheapest first:

1. PubMed publication types give exactly one study type, and it is the slot's
   (`esummary`; mixed types such as a trial also typed as a review are refused).
2. The article has a PMC copy. Its newest version's metadata JSON in the **PMC Cloud Service**
   (`https://pmc-oa-opendata.s3.amazonaws.com/PMC….N/PMC….N.json`, the primary licence source
   per decisions.md §1.1 addendum) says Open Access, not an author manuscript, not retracted,
   and its `license_code` permits rewriting without a non-commercial restriction.
3. The JATS downloads intact (MD5 checked against that metadata) and parses safely (`rbcore.jats`).
4. The JATS `article-type` agrees with the study type, and the paper's **own abstract names the
   design** ("randomized", "randomly assigned", "cohort", "cross-sectional", "systematic review",
   "meta-analysis", or for lab work "mice", "cells", ...). Trial slots also refuse abstracts that
   describe a secondary or post hoc analysis. This step exists because publication types alone
   mislabelled sub-studies and modelling papers in a first run.
5. It has an expert lay summary, a body of 2,500–12,000 words and (except reviews) a Discussion
   or Conclusions section.
6. The §1.1 gate (`rbcore.licences.decide`) over the PMC `license_code` **together with** the
   JATS licence evidence grants display and rewrite with **no review flag**: a disagreement
   between the two fails closed, and so does any unattached part-level `<permissions>` block.

**Licence evidence recorded per candidate:** `licence_field` (`pmc:license_code`),
`licence_raw_value`, `licence_url` (the metadata JSON), `licence_retrieved` (the UTC date the
response was fetched, taken from the **modification time of its cache file**), plus the JATS
licence fields for cross-checking.

## Reproducibility

The config, seed and year range are fixed and every response is cached, so rerunning against the
same cache reproduces `candidates.csv` byte for byte. Two caveats:

- Against a fresh cache it reproduces unless PubMed or PMC changed the records (new article
  versions, retractions, re-indexing) or, for the five slots whose pool is truncated at 500,
  E-utilities' default order changed which 500 PMIDs it returns.
- `licence_retrieved` is the cache file's modification date. Copying the cache without
  preserving modification times, or rebuilding it, changes that column although the evidence
  itself did not change.

## Known limitations (read before approving)

- **Dataset membership is not verified.** The HF dataset is a ~1.6 GB Google Drive release behind
  a loading script and was not downloaded, so a candidate is "in the dataset family" (same
  journals, has an expert lay summary), not confirmed to be a row of the published splits.
- **The review stratum is in practice systematic reviews and meta-analyses.** Narrative reviews
  in these journals do not carry author summaries or digests, so they fail the lay-summary
  requirement. If narrative reviews matter, set `require_lay_summary: false` on the review slots.
- **Classification is metadata-based.** Publication types, JATS article type and a design phrase
  in the abstract must all agree, but nobody has read the papers. A candidate can still be, for
  example, a trial report whose passage is mostly mechanistic.
- **Look twice at these before approving** (judged from titles and metadata only):
  - **S03 A** (placebo response across trials) and **S03 B** (a correlational analysis set in
    the Rakai male-circumcision trial) use trial data but are not primary trial reports.
  - **S06 A** (phylodynamic modelling) is typed observational/cohort.
  - **S06 B** (PMC6426266, desialylation of platelets induced by Von Willebrand Factor as a
    mechanism of platelet clearance in dengue, PLoS Pathogens) may be mainly a mechanistic/lab
    paper that carries PubMed's "Observational Study" type and the word "observational" in its
    abstract.
  - **S10 A** (living with relatives offsets the harm caused by pathogens) and **S10 B**
    (meta-analysis of status signalling in house sparrows) are ecology meta-analyses: life
    science, but not biomedical like every other slot. If the review stratum should be
    biomedical, add a MeSH restriction to the eLife review query and rerun `rbbench select`.
  - **S12 B** (dosing model) is a pharmacometric meta-analysis.
- **Passages are proposed separately**, at ingest (`rbbench ingest`), as the first run of
  rewritable paragraphs of the Discussion (else Results, else body start) totalling 350–650
  words. They are PROPOSED too.
