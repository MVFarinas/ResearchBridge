# Track R (first half): readability and prior-knowledge burden scores

Branch `track-r-readability` (from `phase-0-foundations`), built 2026-10-13 in an unattended run.
Scope: the first half of Plan.md "Track R" and decisions.md §2.4:

- both scores and their pipelines;
- validation 1 on real data;
- the data formats, loaders and evaluation code that validation 2 and the burden validation
  will use once human data exists.

**Both scores are PROVISIONAL**: unvalidated against people, and not for display.

## What was built

| Area | What | Where |
|---|---|---|
| Package | `rbscores` (distribution `researchbridge-scores`), discovered by the Makefile, locked in `requirements/dev.txt`, mypy strict. | `scores/` |
| Text units | JATS via `rbcore.jats` (stable paragraph IDs) or plain text. Units are paragraphs, sections (each abstract; each top-level body section including its subsections; loose body paragraphs as `body`) and the paper (body only). | `rbscores.text` |
| NLP | spaCy `en_core_web_sm` 3.8.0, NER excluded, loaded once; the pipeline is configurable with `RB_SCORES_SPACY_MODEL`. | `rbscores.nlp` |
| Familiarity | wordfreq Zipf frequencies; letter-digit codes looked up by their letters (IL-6 counts as unseen, COVID-19 as "covid"); De-Jargonizer bands reimplemented (common > 1,000 per 90M words, i.e. Zipf 4.05; rare < 50, i.e. Zipf 2.74); a burden weight that is linear between Zipf 4.0 (weight 0) and 1.5 (weight 1). | `rbscores.familiarity` |
| Readability | Per-sentence counts pooled per unit: words per sentence, dependency depth, nominalisations per 100 words (suffix heuristic with a stop list), share of sentences with a passive clause, and jargon density (rare + 0.5 × mid) / words. Composite: mean of z-scores against packaged reference statistics, equal weights. Flesch-Kincaid grade as a baseline only. | `rbscores.readability` |
| Burden | Terms (noun-phrase cores from the first unfamiliar word to the head, abbreviations, unfamiliar single words; citations, figure references and full reference strings skipped). Definitions, found document-wide: Schwartz-Hearst abbreviations; "defined as", "refers to", "means", "stands for"; "known as", "called", "termed"; copular "X is a Y that ..." and "X, which is a Y"; determiner-marked, adjacent appositives outside lists; noun-phrase glosses "X (Y)" and "X, or Y," that are not stock phrases, statistics, numbers, lists or bare names. Citation markers (numeric and author-year, including eLife's unbracketed "Smith et al., 2020"). Weighting: each unfamiliar word counted once per unit, defined terms and words removed, plus 0.5 per citation, per 1,000 words. | `rbscores.burden` |
| Ranked-term API | `rank_undefined_terms(document)`: undefined, unfamiliar terms across the whole document (abstracts included), with weight, count, and every location (paragraph ID and character offsets). This is the hook for Phase 3 annotation targeting. | `rbscores.scoring` |
| Reports | `ScoreReport` per paragraph, section and paper; `to_dict()` JSON with the provisional notice, method version, reference version, model, and every definition found. | `rbscores.scoring` |
| Validation 1 | Download (Hugging Face rows API via `PoliteFetcher`, cached in `data/`), detokenising, abstract/lay pairs, calibration windows, reference statistics, scoring in full and length-matched, Wilson intervals, sign tests, exact McNemar paired comparisons, failure analysis, markdown tables. | `rbscores.validation1`, `scores/reports/` |
| Human data | Two versioned JSON formats with validators (every problem reported at once, pseudonymous rater IDs enforced, a required `synthetic` flag, mark offsets checked against the text) and evaluation code. Pairwise: agreement per judgement and per majority, plus inter-rater agreement. Marks: term-level Spearman and AUC, list precision and recall, passage-level Spearman. Synthetic examples sit in the docs and are validated by the tests. | `rbscores.human_data`, `docs/data-formats/` |
| CLI | `rbscores score`, `terms`, `validation1 download/calibrate/run`, `human validate/evaluate`. Expected user errors (missing or non-UTF-8 input, broken JATS, malformed reference JSON, an over-long paragraph, a missing model, validation steps run before the download) exit 1 with one line on standard error. | `rbscores.cli` |
| Statistics | Wilson interval, exact sign test, average ranks, Pearson, Spearman, AUC and median, without SciPy. | `rbscores.stats` |
| Tests | 237 pytest tests covering every module, including parametrised regression cases for every definition false positive found in review. They use the real spaCy model and wordfreq data, synthetic familiarity tables, synthetic Hugging Face pages (`httpx.MockTransport`), real CC BY JATS fixtures from rbcore, and the synthetic format examples. No network. | `scores/tests/` |

## Validation 1 results (real data)

Lay summary versus abstract, on 241 eLife and 1,376 PLOS validation-split pairs (Goldsack et
al. corpora, CC BY 4.0). Each figure is the share of pairs where the lay summary scores easier,
with its 95% Wilson interval. Full report: [scores/reports/validation_1.md](../../scores/reports/validation_1.md).

| Metric | eLife | PLOS | Pooled | Pooled, length-matched |
|---|---|---|---|---|
| Composite readability | 88.8% [84.2, 92.2] | 66.9% [64.3, 69.3] | 70.1% [67.9, 72.3] | 69.0% [66.7, 71.2] |
| Burden | 99.6% [97.7, 99.9] | 70.9% [68.5, 73.3] | 75.2% [73.0, 77.2] | 82.6% [80.6, 84.3] |
| Jargon density alone | 99.6% | 79.4% | 82.4% | 83.6% |
| Flesch-Kincaid (baseline) | 95.0% | 59.0% | 64.4% | 63.1% |

What the results show:

- §2.4's expectation, "the lay version scores easier in nearly every pair", holds for eLife
  digests. It does not hold for PLOS author summaries.
- Sentence length, syntactic depth and passive voice do not separate the genres. eLife digests
  are *more* passive than their abstracts.
- So the equal-weight composite is significantly worse than jargon density alone (McNemar
  p < 0.001).
- Detecting definitions does not help in this test: abstracts define about as many terms as
  lay summaries, mostly abbreviations. Ignoring definitions is still slightly better when
  length-matched (85.0% vs 82.6% pooled, p < 0.001), after the fix below.
- None of this is a human-difficulty result. The "truth" is a genre label.

## Definition-detection precision (review fix round 1)

Review found that definition detection was net harmful: stock parentheticals ("data not
shown", "arrows", "Methods", "wild type"), comma lists of journal names, proper names, clauses
and citation authors were recorded as definitions and removed real terms from the burden score.
The detector was tightened (see the module docstring of `rbscores.burden.definitions`) and its
precision measured by hand. Full method and every labelled detection:
[scores/reports/definition_precision.md](../../scores/reports/definition_precision.md).

| Sample | Precision (95% Wilson CI) |
|---|---|
| Committed JATS fixtures, old detector (all 85 detections) | 42.4% (32.4-53.0) |
| Same fixtures, new detector (all 37; inspected during the fix, so optimistic) | 83.8% (68.9-92.3) |
| **Held-out validation-split sample, new detector (50 detections)** | **88.0% (76.2-94.4)** |

Abbreviations were 28 of 29 correct in the held-out sample; the other kinds 16 of 21 (76%), with
parenthetical glosses the weakest (2 of 6). One labeller, no agreement figure; recall
unmeasured. The burden score's definition step should not be relied on beyond this until the
"terms I don't know" study measures whether defined terms really cost readers nothing.

## Review fix round 2

- **Names in attribution sentences are no longer terms.** An eLife Insight's "Now, in eLife,
  Rut Carballido-López and colleagues ... including Wei Mao (Université Paris-Saclay)" put
  "carballido", "université paris saclay" and "elife" in the top 20 of the ranked-term list.
  Three patterns now exclude such names (`rbscores.burden.references.find_personal_names`):
  names before "and colleagues" (and similar), "Surname et al." without a year, and a
  parenthesised affiliation with a capitalised institution word, together with the names
  before it. A JATS document's own journal title and NLM abbreviation are not terms where the
  text mentions them (`TextDocument.names`). NER is still not used (decision 4). On the five
  committed fixtures these changes removed only names (eLife Insight: 7 keys; PLOS Medicine:
  "plos medicine") and changed no definition or citation count.
- **More stock parentheticals** (colour and marker combinations such as "black arrowheads",
  controls, vehicle, scale and error bars, open or filled symbols, insets, log-rank) are not
  glosses.
- **Lower-case Schwartz-Hearst short forms need word initials.** In the "long form (SF)" order
  a short form with no capital or digit must contain the first letters of the long form's
  words in order ("base pairs (bp)"), so "increased in hepatocytes (inset)" is no
  abbreviation. *Deviation from the review's suggestion* (a word-frequency guard): wordfreq
  cannot separate the cases, as "inset" (Zipf 2.85) is rarer than "bp" (3.83).
- **Recall fixes.** "Mean", "median" and "CI" count as statistics only in a statistical shape,
  so "carpal tunnel syndrome (compression of the median nerve)" is a gloss again. A numbered
  name ("trisomy 21", one or two digits after a word that is not all capitals) may be the
  defined side of a gloss, never the explanation; quantities ("EUR 5000", "12 mice") still
  rule a parenthetical out.
- **"X and Y, YEAR" needs the comma** to be a citation (eLife house style), so "the Wnt and
  Notch 2019 consortium" is not one.
- **`make test` and `make typecheck` now fail on the first failing package** under macOS's
  GNU Make 3.81, which ignores `.SHELLFLAGS`. This is a Phase 0 issue; it is recorded in
  Phase 0's notes and fixed on this branch.
- Validation 1 was re-run: only burden rows moved, by at most 0.1 points (tables updated).
  The 88.0% definition precision was measured before these changes and was not re-measured.

## How to run

```sh
make setup && make check                      # lint, typecheck, tests (no network needed)
.venv/bin/rbscores score libs/rbcore/tests/fixtures/jats/plos-pmed-1004542.xml
.venv/bin/rbscores validation1 download       # about 20 polite requests, cached under data/
.venv/bin/rbscores validation1 run --output /tmp/v1.json --markdown /tmp/v1.md
```

## Decisions and deviations, with reasons

1. **spaCy `en_core_web_sm` rather than scispaCy.** scispaCy's `en_core_sci_sm` 0.5.4 has CC BY-SA
   3.0 weights (allowed, but share-alike obligations) and requires spaCy < 3.8. The small
   general model is MIT. The pipeline is configurable, and the inventory records the decision.
2. **The model is installed by the lock file from spaCy's GitHub release** (a direct-URL
   dependency in `scores/pyproject.toml`), so `make setup` and CI get it reproducibly and it is
   never committed. It is a 12 MB download from github.com; the existing CI job already has
   network access for PyPI, so nothing changes there. The lock has no hashes (a Phase 0
   choice), so the wheel's SHA-256 is recorded in docs/licence-inventory.md; a release asset
   can be replaced in a way a PyPI file cannot. Switching `make lock` to `--generate-hashes`
   repository-wide would close that gap when the lock policy is next revisited.
3. **wordfreq for familiarity, with its CC BY-SA 4.0 data** used only through lookups. The
   reasoning, the obligations if we ever ship a derived word list, and the rejected
   alternatives are in docs/licence-inventory.md.
4. **NER is not used.** spaCy's small model tagged technical words as people and places
   ("Pyrexia" as PERSON, "HeLa" as GPE). Excluding named entities would have hidden real terms.
   An unusual name in running text therefore counts as a term; citations are skipped by
   pattern instead.
5. **Composite reference: fixed statistics, not batch z-scores.** A text's score does not depend
   on what else is scored. The statistics come from training-split body text, disjoint from
   validation 1's papers. Equal weights are a placeholder; validation 1 shows they are the
   weakest part. They should be refitted on validation 2's human data, not on validation 1
   (which would be circular).
6. **Burden design choices** (none of them in §2.4, all provisional):
   - each unfamiliar *word* counts once per unit, and phrases are only the display unit, so a
     rare word inside several phrases is not counted several times;
   - definitions count document-wide, so a term defined in the abstract is defined everywhere;
   - a citation marker weighs 0.5;
   - a word needs a weight of at least 0.1 to start a term.
7. **The paper unit is the body only.** Abstracts are scored as their own sections, so the
   paper score describes the main text. `rank_undefined_terms` covers abstracts too, because
   readers see them.
8. **Validation data source.** The BioLaySumm 2025 parquet copies (the same authors' release of
   the same splits) were read through the Hugging Face rows API, instead of the tomasg25
   loading script, which downloads two 425 MB Google Drive zips. Licence: the tomasg25 card
   says CC BY 4.0, and the articles are CC BY 4.0 at the publishers. The GitHub repository and
   the BioLaySumm cards state no licence. Details are in the report.
9. **Comparison unit: abstract**, with a length-matched repeat and paired McNemar tests. Both
   were added because lengths differ in opposite directions in the two corpora.
10. **Schwartz-Hearst was written from the paper.** scispaCy's Apache-2.0 `AbbreviationDetector`
    could have been reused, but it would have pulled in the scispaCy package, which pins spaCy
    < 3.8. ScholarPhi (Apache-2.0) was not reused: it is a LaTeX-based neural pipeline. **No
    third-party code was copied or adapted**, so `third_party/` has nothing new. Reuse was
    through published packages only (spaCy, the English model, wordfreq).
11. **Development touched the validation split.** A 40-pair trial run per corpus, and a look at
    a few random pairs, came before four burden fixes (determiner-marked appositives,
    once-per-word counting, the minimum starting weight, cutting cores at determiners). The
    fixes were for errors seen in the output, not for the scores, but this is disclosed in the
    report as a limitation. Review fix round 1 tightened definition detection again, developed
    on the committed fixtures and 80 inspected validation-split pairs; its precision was then
    measured on 120 other pairs, and validation 1 was re-run.
12. **Final definitions are not yet recorded in decisions.md.** Plan.md does that at the end of
    Track R, after the human validations.
13. **Statistics are implemented in-house** (`rbscores.stats`, tested against published and
    hand-computed values) rather than adding SciPy for five functions.
14. **Schwartz-Hearst, one tightening of the paper.** In the "SF (long form)" order the short
    form must look like an abbreviation (two capitals, or a capital and a digit), not merely
    contain a capital, so "Best (but the results were inconsistent)" is not an abbreviation.
    A two-word parenthetical that is not a valid short form ("ATP (adenosine triphosphate)") is
    tried in that order too. Short forms inside citations are ignored.
15. **Reference strings are excluded, boxed text is not.** The eLife Insight's "Related research
    article" box put author surnames at the top of the ranked-term list. Excluding all
    `boxed` paragraphs would also drop glossary boxes, which hold definitions, so a
    reference-string detector (three or more "Surname AB" authors and a year, through a
    following DOI) excludes the reference instead.
16. **Input limits.** Plain-text files over 5 MB (was 20 MB) and paragraphs over 100,000
    characters are refused with the package's own error; spaCy refuses texts over 1,000,000
    characters, and real paragraphs are a few thousand.

## Pending the owner (manual steps)

1. **Collect the human data.**
   - *Validation 2:* lay readers' pairwise "which is harder?" judgements on a held-out passage
     sample, in the format in [docs/data-formats/pairwise-judgements.md](../data-formats/pairwise-judgements.md).
   - *Burden validation:* "terms I don't know" marks, collected in Phase 1's comprehension
     study, in the format in [docs/data-formats/term-marks.md](../data-formats/term-marks.md).
   - Design notes (randomised order, several raters per pair, at least 5 readers per passage,
     pseudonymous IDs) are in those files.
   - Then run `rbscores human evaluate pairwise|marks FILE`.
   - The study needs whatever consent and ethics approval applies to collecting data from
     members of the public.
2. **Ask MedReadMe's authors about their data** (github.com/chaojiang06/medreadme has no
   licence). Ask whether their jargon-span annotations may be used, and under what licence, for
   a possibly commercial product. Until they answer, the data is not used.
3. **After validation 2:** decide the composite's weights. Validation 1 suggests that jargon
   density and nominalisation carry most of the signal. Then record the final definitions of
   both scores in decisions.md, superseding the §2.4 drafts.
4. **Confirm the wordfreq attribution plan** (CC BY-SA 4.0 data) before the scores are shown in
   the product: the scores' credits must name wordfreq and its sources.

## Known limitations

- **No human validation yet.** Validation 1 checks that the scores separate the genres, not
  that they measure difficulty.
- **spaCy's small general model misparses biomedical text.** Depth, passive detection, noun
  chunks and appositives depend on its parses. One misparse ("hepatocytes" as an appositive of
  "Apoptosis") led to the determiner rule for appositives.
- **Familiarity is general-text frequency**, frozen around 2021 (wordfreq stopped updating in
  2024). An everyday word with a technical sense ("significant", "power") counts as familiar.
  A phrase made of common words ("cell wall", "fixed effects") is not a term.
- **Definition detection is heuristic.** Precision is 88.0% (76.2-94.4) on a held-out sample of
  50; recall is unmeasured. It misses definitions spread across sentences, dashes, and
  definitions in figures. Remaining false hits include field labels after list items
  ("synapses (neuroscience)") and glosses read in the wrong direction.
- **Nominalisation detection is a suffix heuristic.** It misses zero-derived nouns ("a change")
  and gerunds.
- **Burden per 1,000 words depends on length**, because terms count once per unit. Compare units
  of similar length.
- **Names outside the recognised patterns still count as terms**: a researcher named without
  "and colleagues", "et al." or an affiliation ("as Carballido-López showed"), another
  journal's name, or a place. Proper names are a disclosed limitation of not using NER.
- **Citation patterns** cover numeric brackets and author-year forms only. Superscript citations
  lose their marking in JATS flattening and are not counted.
- **Validation 1 caveats:** corpus tokenisation artefacts; truncation keeps the opening of the
  longer text; there is no multiple-comparison correction; and development touched the
  validation split (decision 11).
- **The ranked-term API reports character offsets into plain paragraph text.** Mapping them to
  rendered HTML (W3C selectors) is Phase 4's job, as in Phase 0's notes.
