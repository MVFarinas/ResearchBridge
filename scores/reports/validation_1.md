# Validation 1: do lay summaries score easier than their abstracts?

**Status: PROVISIONAL.** Both scores are draft definitions (decisions.md §2.4). This is the
first of their validations and uses no human judgements; it cannot show that either score
tracks what lay readers find hard. Nothing here should be displayed to readers.

Run on 2026-10-13 with `rbscores` method `rbscores-0.1-provisional`, reference statistics
`reference-v0-2026-10-13-provisional`, spaCy `en_core_web_sm-3.8.0` and wordfreq 3.1.1. Every
number below comes from [validation_1_results.json](validation_1_results.json); the tables are
inserted verbatim from [validation_1_tables.md](validation_1_tables.md), both written by
`rbscores validation1 run`.

## Summary

- **Readability composite:** ranks the lay summary easier in **88.8%** of eLife pairs (95% CI
  84.2-92.2) and **66.9%** of PLOS pairs (64.3-69.3); 70.1% pooled (67.9-72.3). Length-matched:
  90.5%, 65.2% and 69.0%.
- **Burden:** **99.6%** of eLife pairs (97.7-99.9) and **70.9%** of PLOS pairs (68.5-73.3);
  75.2% pooled. Length-matched: 97.9%, 79.9% and 82.6%.
- decisions.md §2.4 expected the lay version to score easier "in nearly every pair". That holds
  for eLife digests on both scores. It does not hold for PLOS author summaries, on either score.
- **Jargon density alone beats the composite** (82.4% vs 70.1% pooled; exact McNemar
  p < 0.001). Sentence length, syntactic depth and passive-voice rate barely separate the two
  kinds of text, and eLife digests use *more* passive voice than their abstracts (lay easier in
  only 33.2% of pairs). With equal weights, these three features dilute the two that work.
- **The composite beats Flesch-Kincaid on PLOS** (66.9% vs 59.0%, p < 0.001) **but not on
  eLife** (88.8% vs 95.0%, p = 0.006).
- **Definition detection does not help here.** Ignoring definitions makes no significant
  difference on full texts (pooled p = 0.378) and is slightly better when length-matched (85.0%
  vs 82.6%, p < 0.001). Abstracts define about as many terms as lay summaries, mostly
  abbreviations, so this test cannot reward definition detection. Whether a defined term
  really costs readers nothing is a question for the "terms I don't know" study. The
  detector's precision was measured separately: 88.0% (95% CI 76.2-94.4) on a held-out,
  hand-labelled sample of 50 detections ([definition_precision.md](definition_precision.md)).

## Question and comparison unit

Each record pairs a research article with a lay summary of it. If either score measures
difficulty, it should rank the lay summary as easier than the article's technical text in most
pairs.

**Comparison unit: lay summary versus abstract.** Both are short summaries of the same paper
written for different readers, so topic, field and the paper's own terminology are held
roughly constant. Comparing with the full article would mostly measure length and section mix
(methods sections are hard in ways a summary never is), and would also confound every per-word
rate with a tenfold length difference.

The lengths still differ: eLife digests are about twice as long as their abstracts (median 355
vs 153 words), and PLOS author summaries are shorter (186 vs 251). Length matters most for
burden, because each unfamiliar word counts once per text, so a longer text has fewer *new*
unfamiliar words per 1,000 words. Every comparison is therefore repeated **length-matched**:
the longer text is cut to whole sentences, keeping the prefix whose word count is closest to
the shorter text's.

## Data

| | eLife | PLOS |
|---|---|---|
| Dataset (Hugging Face) | `BioLaySumm/BioLaySumm2025-eLife` | `BioLaySumm/BioLaySumm2025-PLOS` |
| Revision downloaded | `144e9c785e3a309da804eb6786feb38e6596f390` | `b3fd4cbdf3f1defac6b0d5f5557652ce2d65ad16` |
| Pairs: validation split, all rows | 241 | 1,376 |
| Rows skipped (no "Abstract" first section, empty or truncated text) | 0 | 0 |
| Calibration: first 100 training-split articles | 385 windows | 387 windows |
| Lay summary | eLife digest, written by eLife editors | Author summary, written by the authors |

**Source and licence.** The corpora are Goldsack et al., "Making Science Simple: Corpora for
the Lay Summarisation of Scientific Literature", EMNLP 2022. Checked on 2026-10-13:

- The authors' Hugging Face card (`tomasg25/scientific_lay_summarisation`, revision
  `9e109bef`) declares **CC BY 4.0**.
- The texts are PLOS and eLife research articles, which both publishers release under
  **CC BY 4.0** (a few PLOS articles under CC0).
- The authors' GitHub repository (`TGoldsack1/Corpora_for_Lay_Summarisation`) has no licence
  file. The BioLaySumm 2025 copies used here have no licence on their cards. They are the same
  authors' shared-task release of the same training and validation splits (the eLife
  validation split has the same number of records, 241).
- We rely on the CC BY 4.0 of the underlying articles and of the authors' own card. We only
  downloaded the data for local evaluation, into the gitignored `data/` directory. No article
  text is committed, apart from the short term and explanation strings quoted, with
  attribution, in [definition_precision.md](definition_precision.md). The failure examples
  below quote paper titles as attribution; every pair's ID and title is recorded in
  validation_1_results.json.

We did not check each paper's licence at its primary source (decisions.md §1.1). That check
matters for papers we display or rewrite. It does not matter for local scoring.

**Download.** The data was fetched through the Hugging Face dataset viewer's `/rows` API
(JSON pages of 100 rows) using `rbcore.http.PoliteFetcher`: at most one request per second,
cached and resumable, with the project's neutral User-Agent. Rows the API returned with
truncated cells would have been skipped; there were none. The tomasg25 copy is a loading script
that downloads two 425 MB zips from Google Drive, which is far more than a sample needs. The
test splits were not used, because their lay summaries are withheld.

**Preparation.** The corpus texts were sentence-tokenised and re-joined with spaces ("C .
elegans", "1 . 9 billion"). `detokenise` restores normal spacing so that spaCy segments
sentences correctly. The abstract is the article's first section; the PLOS and eLife records
all have "Abstract" as their first heading. Lay-summary paragraphs are kept apart.

## Method

**Scores.** Each text is scored as one unit, exactly as `rbscores` scores a paper:

- The five readability features (sentence length, dependency depth, nominalisations per 100
  words, share of sentences with a passive clause, and De-Jargonizer jargon density).
- The composite: the mean of the five z-scores, with equal weights.
- The burden score (undefined unfamiliar words plus 0.5 per citation marker, per 1,000 words).
- The burden score with definition detection switched off, as an ablation.
- The Flesch-Kincaid grade, as a familiar baseline that is not part of either score.

The composite's reference statistics come from 772 windows of body text: the opening ~150 words
of up to four body sections in each of the first 100 *training*-split articles of each corpus.
Those articles are disjoint from the validation-split papers scored here. No lay summary was
used for calibration, so the calibration never saw which texts are "easy". The statistics are
packaged as `rbscores/readability/reference_v0.json`.

**Statistics.** For each metric, a pair counts as correct when the lay summary has the strictly
lower value. Ties count as incorrect, which is conservative, and are reported. The share
correct has a 95% Wilson score interval. Metrics are compared with each other on the same pairs
using an exact McNemar test, a two-sided sign test on the pairs that exactly one metric gets
right. The p-values are not adjusted for the number of metrics.

## Results

<!-- BEGIN GENERATED TABLES (rbscores validation1 run --markdown) -->

Share of pairs where the lay summary scores easier, with its 95% Wilson interval; ties count as
incorrect.

### Full texts

| Metric | eLife (n = 241) | PLOS (n = 1376) | Pooled (n = 1617) |
|---|---|---|---|
| Sentence length | 53.9% [47.6, 60.1] | 57.0% [54.3, 59.6]; 2 ties | 56.5% [54.1, 58.9]; 2 ties |
| Syntactic depth | 47.3% [41.1, 53.6]; 2 ties | 50.0% [47.4, 52.6]; 19 ties | 49.6% [47.2, 52.0]; 21 ties |
| Nominalisation rate | 91.7% [87.5, 94.6] | 57.1% [54.5, 59.7] | 62.3% [59.9, 64.6] |
| Passive-voice rate | 33.2% [27.6, 39.4]; 5 ties | 48.5% [45.9, 51.2]; 65 ties | 46.3% [43.8, 48.7]; 70 ties |
| Jargon density | 99.6% [97.7, 99.9] | 79.4% [77.2, 81.5] | 82.4% [80.5, 84.2] |
| **Composite readability** | 88.8% [84.2, 92.2] | 66.9% [64.3, 69.3] | 70.1% [67.9, 72.3] |
| **Burden** | 99.6% [97.7, 99.9] | 70.9% [68.5, 73.3] | 75.2% [73.0, 77.2] |
| Burden, definitions ignored (ablation) | 100.0% [98.4, 100.0] | 71.6% [69.1, 73.9] | 75.8% [73.7, 77.8] |
| Flesch-Kincaid grade (baseline, not ours) | 95.0% [91.5, 97.1] | 59.0% [56.4, 61.6] | 64.4% [62.0, 66.7] |

### Length-matched (longer text cut to whole sentences)

| Metric | eLife (n = 241) | PLOS (n = 1376) | Pooled (n = 1617) |
|---|---|---|---|
| Sentence length | 59.8% [53.5, 65.7]; 3 ties | 53.9% [51.2, 56.5]; 16 ties | 54.7% [52.3, 57.1]; 19 ties |
| Syntactic depth | 53.1% [46.8, 59.3]; 7 ties | 45.8% [43.2, 48.4]; 41 ties | 46.9% [44.5, 49.3]; 48 ties |
| Nominalisation rate | 91.7% [87.5, 94.6] | 53.2% [50.6, 55.8]; 6 ties | 58.9% [56.5, 61.3]; 6 ties |
| Passive-voice rate | 33.2% [27.6, 39.4]; 21 ties | 48.2% [45.6, 50.8]; 136 ties | 45.9% [43.5, 48.4]; 157 ties |
| Jargon density | 99.6% [97.7, 99.9] | 80.8% [78.6, 82.8]; 3 ties | 83.6% [81.7, 85.3]; 3 ties |
| **Composite readability** | 90.5% [86.1, 93.6] | 65.2% [62.6, 67.7] | 69.0% [66.7, 71.2] |
| **Burden** | 97.9% [95.2, 99.1] | 79.9% [77.7, 81.9] | 82.6% [80.6, 84.3] |
| Burden, definitions ignored (ablation) | 97.9% [95.2, 99.1] | 82.8% [80.7, 84.7] | 85.0% [83.2, 86.7] |
| Flesch-Kincaid grade (baseline, not ours) | 96.7% [93.6, 98.3] | 57.3% [54.6, 59.9]; 2 ties | 63.1% [60.8, 65.5]; 2 ties |

### Paired comparisons (exact McNemar test on discordant pairs)

| Comparison | Group | Both right | Only first | Only second | Neither | p |
|---|---|---|---|---|---|---|
| Composite readability vs Flesch-Kincaid grade (baseline, not ours), full | eLife | 208 | 6 | 21 | 6 | 0.006 |
| Composite readability vs Jargon density, full | eLife | 214 | 0 | 26 | 1 | < 0.001 |
| Burden vs Burden, definitions ignored (ablation), full | eLife | 240 | 0 | 1 | 0 | 1.000 |
| Composite readability vs Flesch-Kincaid grade (baseline, not ours), full | PLOS | 705 | 215 | 107 | 349 | < 0.001 |
| Composite readability vs Jargon density, full | PLOS | 770 | 150 | 323 | 133 | < 0.001 |
| Burden vs Burden, definitions ignored (ablation), full | PLOS | 929 | 47 | 56 | 344 | 0.431 |
| Composite readability vs Flesch-Kincaid grade (baseline, not ours), full | Pooled | 913 | 221 | 128 | 355 | < 0.001 |
| Composite readability vs Jargon density, full | Pooled | 984 | 150 | 349 | 134 | < 0.001 |
| Burden vs Burden, definitions ignored (ablation), full | Pooled | 1169 | 47 | 57 | 344 | 0.378 |
| Composite readability vs Flesch-Kincaid grade (baseline, not ours), matched | eLife | 213 | 5 | 20 | 3 | 0.004 |
| Composite readability vs Jargon density, matched | eLife | 218 | 0 | 22 | 1 | < 0.001 |
| Burden vs Burden, definitions ignored (ablation), matched | eLife | 235 | 1 | 1 | 4 | 1.000 |
| Composite readability vs Flesch-Kincaid grade (baseline, not ours), matched | PLOS | 668 | 229 | 120 | 359 | < 0.001 |
| Composite readability vs Jargon density, matched | PLOS | 755 | 142 | 357 | 122 | < 0.001 |
| Burden vs Burden, definitions ignored (ablation), matched | PLOS | 1082 | 17 | 57 | 220 | < 0.001 |
| Composite readability vs Flesch-Kincaid grade (baseline, not ours), matched | Pooled | 881 | 234 | 140 | 362 | < 0.001 |
| Composite readability vs Jargon density, matched | Pooled | 973 | 142 | 379 | 123 | < 0.001 |
| Burden vs Burden, definitions ignored (ablation), matched | Pooled | 1317 | 18 | 58 | 224 | < 0.001 |

### Median word counts

| Group | Lay | Abstract | Lay, matched | Abstract, matched |
|---|---|---|---|---|
| eLife | 355 | 153 | 153 | 153 |
| PLOS | 186 | 251 | 181 | 181 |
| Pooled | 193 | 235 | 174 | 173 |

### Median term counts per text (full texts)

| Group | Lay undefined | Abstract undefined | Lay defined | Abstract defined |
|---|---|---|---|---|
| eLife | 13 | 20 | 3 | 1 |
| PLOS | 17 | 25 | 1 | 2 |
| Pooled | 16 | 24 | 1 | 2 |

### Median values (full texts)

| Metric | eLife lay | eLife abstract | PLOS lay | PLOS abstract |
|---|---|---|---|---|
| Sentence length | 22.39 | 22.14 | 23.88 | 24.75 |
| Syntactic depth | 7.56 | 7.40 | 7.89 | 7.89 |
| Nominalisation rate | 3.12 | 6.76 | 6.19 | 6.70 |
| Passive-voice rate | 0.32 | 0.22 | 0.29 | 0.29 |
| Jargon density | 0.10 | 0.20 | 0.14 | 0.17 |
| **Composite readability** | -0.51 | 0.00 | -0.04 | 0.11 |
| **Burden** | 11.84 | 62.31 | 41.67 | 51.49 |
| Burden, definitions ignored (ablation) | 16.98 | 68.41 | 45.12 | 55.80 |
| Flesch-Kincaid grade (baseline, not ours) | 13.15 | 16.94 | 16.73 | 17.11 |

<!-- END GENERATED TABLES -->

## Failure analysis

**eLife: 27 composite failures out of 241.** In every one, the digest is longer than its
abstract. Within the failures, the lay text is *higher* than the abstract (median difference in
z-scores) on passive rate (+1.00), syntactic depth (+0.93) and sentence length (+0.62). It is
lower on jargon density (−0.93) and nominalisation (−0.48). None of the 27 fails on burden.
These digests are plainly worded but written in longer, more passive sentences than their
abstracts, which are terse. The worst cases are:

- elife-validation-59, "Impact of nucleic acid and methylated H3K9 binding activities of
  Suv39h1 on its heterochromatin assembly";
- elife-validation-123, "Sodium taurocholate cotransporting polypeptide is a functional receptor
  for human hepatitis B and D virus";
- elife-validation-13, "An effector of the Irish potato famine pathogen antagonizes a host
  autophagy cargo receptor".

Within each corpus, the length ratio does not predict how wrong the composite is (Spearman
0.01 for eLife, 0.02 for PLOS). The pooled −0.19 reflects the difference between the corpora,
not a length effect.

**PLOS: 456 composite failures out of 1,376.** Only 72 of these have a lay text longer than
the abstract. The failures are spread across the syntactic features: in the median failure the
lay text is higher on depth (+0.61 SD), sentence length (+0.36), passive rate (+0.35) and
nominalisation (+0.26), and only jargon (−0.30) points the right way. Burden also fails on 163
of the 456. PLOS author summaries are written by the authors, and Goldsack et al. (2022)
describe them as shorter and more technical than eLife digests; these results agree. In the
worst failures the author summary is denser than the abstract on the syntactic features. Examples:

- plos-validation-1137, "Pneumococcal Competence Coordination Relies on a Cell-Contact Sensing
  Mechanism" (lay 122 words, abstract 225);
- plos-validation-1223, "State–Space Forecasting of Schistosoma haematobium Time-Series in
  Niono, Mali".

Some of these pairs may be ones where the lay summary really is no easier. A genre label is
not a difficulty judgement.

**What this means for the definitions.**

- **The composite's equal weights are the main problem.** Jargon density and nominalisation
  carry most of the signal in this corpus. Sentence length, depth and passive rate carry
  little or none, or point the wrong way. This is one corpus, and the "truth" is a genre
  label, so the weights should not be refitted here: lay summaries are partly *defined* by
  avoiding jargon, which would make a refit circular. Validation 2's human pairwise judgements
  are the right data for fitting weights. Until then, report the features separately and
  treat the composite as the weakest part of the readability score.
- **The burden score separates the genres better than the composite** (75.2% vs 70.1% pooled,
  and 82.6% length-matched). It does so mainly through word familiarity, which overlaps with
  jargon density by design (decisions.md §2.4 lists jargon under readability and unfamiliar
  terms under burden). What keeps the two scores separable is that burden subtracts defined
  terms, counts each unfamiliar word once, and adds citations. Validation 1 gives no evidence
  yet that those parts add value.

## Limitations

- **The ground truth is a genre, not a judgement.** "Lay summary" means "written for lay
  readers", not "found easier by lay readers". Guo et al. (2025) found that summaries with
  better formula scores could produce worse comprehension. Validation 1 checks that the scores
  separate the genres. It does not check that they measure difficulty.
- **Partial overlap between development and evaluation data.** During development, a trial run
  on the first 40 pairs of each corpus's validation split, and inspection of a few random
  pairs, preceded four changes to the burden pipeline:
  - appositives now count as definitions only when a determiner marks the explaining side;
  - each unfamiliar word now counts once per text;
  - a word needs a weight of at least 0.1 to start a term;
  - a term's core now starts after a determiner.

  These changes were made because inspected outputs were wrong (for example, one technical term
  "defined" by another), not to raise the scores. In review fix round 1, definition detection
  was tightened again (stock parentheticals, lists, names and clauses are no longer definitions;
  see [definition_precision.md](definition_precision.md)) and unbracketed eLife citations
  ("Smith et al., 2020") became citation markers. Those changes were developed on the committed
  JATS fixtures and on 80 inspected validation-split pairs, and every number here was then
  re-run. Review fix round 2 (more stock figure idioms, numbered-name and "median" glosses,
  researchers' names, affiliations and the journal title excluded from terms, and the comma
  required in "X and Y, YEAR") was developed on the committed fixtures and hand-written
  sentences only, and every number was re-run again; only burden rows moved, by at most 0.1
  points in share correct. Even so, the validation split was not strictly held out. A fresh sample, such as training-split pairs not used for calibration,
  should confirm the numbers.
- **Corpus artefacts.** The texts went through the corpus's tokenisation and our detokenising.
  Superscripts, italics and some symbols were lost, and stray spacing may remain.
- **Tooling.** spaCy's small general-English model misparses biomedical text: dependency depth,
  passive detection, noun chunks and appositives all depend on its parses. Word familiarity
  comes from wordfreq's general web, subtitle, news and book frequencies, frozen around 2021.
  That is not what lay readers know: newer terms look rarer than they are, and an everyday
  word can be technical in context.
- **Burden design choices** are untested provisional settings: the familiarity anchors (Zipf 4.0
  and 1.5), the minimum starting weight of 0.1 and the citation weight of 0.5. Abstracts and lay
  summaries rarely cite, so this test barely exercises the citation part.
- **Length matching** keeps the opening of the longer text. Openings may differ from the rest
  (eLife digests often open with background).
- **Statistics.** Many metrics are compared without correcting for multiple comparisons. The
  intervals are per metric and per corpus. Ties count as failures.

## Reproduce

```sh
make setup
.venv/bin/rbscores validation1 download          # about 20 requests, cached under data/
.venv/bin/rbscores validation1 calibrate \
  --output scores/src/rbscores/readability/reference_v0.json \
  --version reference-v0-2026-10-13-provisional
.venv/bin/rbscores validation1 run \
  --output scores/reports/validation_1_results.json \
  --markdown scores/reports/validation_1_tables.md
```

The download and scoring take a few minutes on a laptop. Per-pair metrics are written to
`data/validation1/per-pair.jsonl`, which is not committed.

## Attribution

The texts are from PLOS and eLife research articles (CC BY 4.0), via the corpora of T. Goldsack,
Z. Zhang, C. Lin and C. Scarton, "Making Science Simple: Corpora for the Lay Summarisation of
Scientific Literature", EMNLP 2022, as redistributed for the BioLaySumm 2025 shared task.
