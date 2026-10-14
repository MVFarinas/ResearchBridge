# Pairwise "which is harder?" judgements (validation 2)

**Schema:** `researchbridge.pairwise-judgements`, **version 1**. **Owner:** Track R
(`rbscores.human_data.pairwise`). **Purpose:** validation 2 of the readability score
(decisions.md §2.4): lay readers see two passages and say which is harder to read. The score
should agree with them on a held-out sample.

One study is one UTF-8 JSON file. A complete example, which the test suite validates, is
[examples/pairwise-judgements.synthetic.json](examples/pairwise-judgements.synthetic.json).

## Fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `schema` | string | yes | Exactly `researchbridge.pairwise-judgements`. |
| `version` | integer | yes | Exactly `1`. A breaking change gets a new version and loader. |
| `study_id` | string | yes | Identifies the study (for example `2027-03-pilot`). |
| `synthetic` | boolean | yes | `true` for made-up data (tests, demos). Synthetic data must never be reported as a result. |
| `description` | string | no | What was done: recruitment, instructions shown, dates. |
| `passages` | array | yes | Every passage shown (see below). |
| `raters` | array | yes | Every rater (see below). |
| `judgements` | array | yes | One entry per rater per pair of passages. |

**Passage:**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `passage_id` | string | yes | Unique in the study; 1-64 of `A-Z a-z 0-9 _ -`. |
| `text` | string | yes | The exact text shown, which is what gets scored. |
| `source.doi` | string | no | DOI of the paper the passage comes from. |
| `source.paragraph_id` | string | no | rbcore paragraph ID (`sec2.1-p3`), when the passage is one paragraph. |
| `source.licence` | string | no | Licence of the passage (SPDX style, e.g. `CC-BY-4.0`). Passages must pass the decisions.md §1.1 display gate before being shown to anyone. |

**Rater:**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `rater_id` | string | yes | A **pseudonym**: 1-64 of `A-Z a-z 0-9 _ -`. Never a name or e-mail address (the pattern rejects `@` and spaces). Keep any key linking pseudonyms to people outside this file. |
| `background` | string | no (default `not_reported`) | Highest education relative to the passages' field: `secondary_or_less`, `university_other_field`, `university_related_field`, `postgraduate_related_field`, `not_reported`. |

**Judgement:**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `rater_id` | string | yes | A listed rater. |
| `passage_a`, `passage_b` | string | yes | Two different listed passages. |
| `harder` | string | yes | `a` (passage_a is harder), `b`, or `same`. |
| `shown_first` | string | no | `a` or `b`: which passage was displayed first (to check order effects). |

Rules checked by the validator: unique passage and rater IDs; references resolve; a passage is
never compared with itself; **one judgement per rater per unordered pair** (re-asking the same
rater is a protocol error, not more data). Every problem in a file is reported at once.

## Study design notes

- Randomise which passage is shown first and record it in `shown_first`.
- Give several raters the same pairs: the evaluation reports how often two raters agree, which
  is the ceiling any score can reach.
- Pair passages of similar length where possible, so raters judge difficulty rather than length.
- Use passages from the faithfulness benchmark where possible (decisions.md §2.4 "reuse with
  §1.4"); comprehension-oriented lay raters suit this task.

## Evaluation

`rbscores human evaluate pairwise FILE` scores every passage with the PROVISIONAL metrics (the
five features, the composite and the burden score) and reports, per metric:

- `judgement_agreement`: share of decisive judgements (`a` or `b`) where the metric gives the
  judged-harder passage the strictly higher value, with a 95% Wilson interval. A metric tie
  counts as a disagreement.
- `majority_agreement`: the same over passage pairs whose decisive votes have a strict majority.
- `rater_agreement`: pairs judged by two or more raters, and the share of rater-pairs giving
  the same verdict (`same` included), as the noise ceiling.

`rbscores human validate pairwise FILE` only checks the file.
