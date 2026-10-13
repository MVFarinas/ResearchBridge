# scores/: readability and prior-knowledge burden scores (Track R)

Python package `rbscores` (distribution `researchbridge-scores`). It implements the two draft
metrics from decisions.md §2.4.

> **PROVISIONAL.** Neither score has been validated against lay readers yet. Every output says
> so. Do not show the scores to readers until validation 2 and the burden validation are done
> and the final definitions are recorded in decisions.md.

The two scores stay separate. **Readability** measures how the text is written. **Burden**
measures what it assumes the reader already knows. They are reported side by side and never
combined.

## The scores

| Score | Definition (v0.1, provisional) | Code |
|---|---|---|
| Readability features | Words per sentence; dependency-tree depth; nominalisations per 100 words; share of sentences with a passive clause; De-Jargonizer jargon density, (rare + 0.5 × mid-frequency) / words, using wordfreq frequencies. Higher means harder. | `rbscores.readability.features` |
| Readability composite | Mean of the five z-scores against fixed reference statistics (772 body-text windows from PLOS and eLife training articles). Equal weights, a placeholder. | `rbscores.readability.composite` |
| Prior-knowledge burden | Undefined technical terms, each unfamiliar word counted once and weighted 0 to 1 by how rare it is in general text, plus 0.5 per citation marker, per 1,000 words. | `rbscores.burden` |

**Burden pipeline.**

1. **Terms** (`burden.terms`): the technical core of each noun phrase (from its first
   unfamiliar word to its head), abbreviations, and unfamiliar single words.
2. **Definitions** found anywhere in the document (`burden.definitions`):
   - Schwartz-Hearst abbreviation pairs (`burden.abbreviations`), implemented from the 2003
     paper;
   - "X is defined as", "X refers to" and "known as X" / "called X";
   - "X is a Y that ..." and "X, which is a Y";
   - appositives ("X, a Y, ...") and glosses ("X (Y)", "X, or Y,").
3. **Citation markers** (`burden.references`): numeric and author-year.
4. **Scoring** (`burden.score`).

`rank_undefined_terms(document)` returns the ranked list of undefined, unfamiliar terms with
paragraph IDs and character offsets. It is meant to drive annotation targeting (Phase 3).

Units are paragraphs (rbcore's stable IDs, such as `sec2.1-p3`), sections (abstracts and
top-level body sections) and the paper (the body text).

## Use

```sh
make setup                                   # installs spaCy, en_core_web_sm and wordfreq into .venv
.venv/bin/rbscores score paper.xml           # JATS (.xml/.nxml) or a UTF-8 text file
.venv/bin/rbscores score paper.xml --json --top-terms 20 --no-paragraphs
.venv/bin/rbscores terms paper.xml --limit 30
.venv/bin/rbscores validation1 download      # then: calibrate, run (see reports/validation_1.md)
.venv/bin/rbscores human validate pairwise study.json
.venv/bin/rbscores human evaluate marks study.json
```

```python
from rbscores import load_document, rank_undefined_terms, score_document

report = score_document(load_document("paper.xml"))
report.paper.composite, report.paper.burden.burden_per_1000
report.to_dict()  # JSON-ready, with the provisional notice
rank_undefined_terms(load_document("paper.xml"), limit=20)
```

## Validation

- **Validation 1** (done, real data): do lay summaries score easier than their abstracts on the
  PLOS and eLife corpora? See [reports/validation_1.md](reports/validation_1.md). In short:
  - eLife pairs: composite 88.8%, burden 99.6%;
  - PLOS pairs: composite 66.9%, burden 70.8%;
  - jargon density alone beats the equal-weight composite.
- **Validation 2** (pending human data): agreement with lay readers' pairwise "which is
  harder?" judgements. Format: [docs/data-formats/pairwise-judgements.md](../docs/data-formats/pairwise-judgements.md).
- **Burden validation** (pending human data): agreement with lay readers' "terms I don't know"
  marks from Phase 1's comprehension study. Format: [docs/data-formats/term-marks.md](../docs/data-formats/term-marks.md).

## Configuration

`RB_SCORES_SPACY_MODEL` chooses another installed spaCy pipeline (default `en_core_web_sm`).
The packaged reference statistics were computed with the default, so a different pipeline
changes the scores. `RB_DATA_DIR` (default `data/`) is where validation downloads go.

Licences of the model, word frequencies and data: [docs/licence-inventory.md](../docs/licence-inventory.md).
Notes, deviations and pending steps: [docs/phase-notes/track-r.md](../docs/phase-notes/track-r.md).
