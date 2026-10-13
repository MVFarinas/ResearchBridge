# "Terms I don't know" marks (burden validation)

**Schema:** `researchbridge.term-marks`, **version 1**. **Owner:** Track R
(`rbscores.human_data.marks`). **Collected by:** Phase 1's comprehension study (Plan.md,
"Comprehension study"), where lay readers also mark the terms they do not know. **Purpose:**
validating the prior-knowledge burden score (decisions.md §2.4): the score, and its ranked list
of undefined unfamiliar terms, should track what readers mark.

One study is one UTF-8 JSON file. A complete example, which the test suite validates, is
[examples/term-marks.synthetic.json](examples/term-marks.synthetic.json).

## Fields

The top-level fields `schema` (exactly `researchbridge.term-marks`), `version` (exactly `1`),
`study_id`, `synthetic`, `description`, `passages` and `raters` are the same as in
[pairwise-judgements.md](pairwise-judgements.md), including the pseudonymous rater IDs and the
passage `source` block. In addition:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `responses` | array | yes | One entry per rater per passage they read. |

**Response:**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `rater_id` | string | yes | A listed rater. |
| `passage_id` | string | yes | A listed passage. |
| `marks` | array | yes | The spans the rater marked as unknown; **an empty list means they read it and knew every term**. A passage the rater never saw has no response. |

**Mark:**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `start` | integer | yes | Character offset in the passage `text` (Unicode code points, as Python indexes strings; 0-based). |
| `end` | integer | yes | End offset, exclusive; `start < end <= len(text)`. |
| `text` | string | yes | Exactly `text[start:end]`. A redundancy check: a mismatch means the offsets were computed against different text (for example after whitespace changes) and the file is rejected. |

Rules checked by the validator: one response per rater per passage; marks inside the text,
matching it, and not overlapping within a response. Every problem is reported at once.

## Collection notes

- Store the passage exactly as shown. If the interface renders HTML, compute offsets against the
  plain text stored here, not against the HTML.
- Let readers mark any span (a word, part of a phrase, a whole phrase). The evaluation counts a
  term as marked when any mark overlaps any of its occurrences, so marking "nephrons" or "a
  million nephrons" both count for the term "nephron".
- Record which passages each reader actually finished; send a response only for those.
- Familiarity varies widely between readers, even within one field (August et al.): collect from
  enough readers per passage (at least 5 is a reasonable start) to estimate a mark *rate*.

## Evaluation

`rbscores human evaluate marks FILE` runs the burden pipeline on each passage, using the exact
passage text so term offsets match mark offsets, and reports:

- **Term level:** for each candidate term, its *mark rate* (share of the passage's respondents
  whose marks overlap it). `spearman_weight_vs_mark_rate` correlates the term's burden weight
  (0 if familiar or defined in the passage) with its mark rate;
  `auc_weight_for_majority_marked` is the AUC of the weight for telling terms marked by at least
  half of respondents from the rest.
- **List quality:** of the terms the pipeline flags (weight above 0), the share marked by anyone
  and by most (`precision_*`); of all readers' marks, the share that fall on a flagged term and
  on any candidate term (`recall_*`). Low candidate recall means the extractor misses what
  readers find hard.
- **Passage level:** `spearman_burden_vs_marks_per_1000` correlates the burden score with the
  mean number of marks per 1,000 words.

`rbscores human validate marks FILE` only checks the file.
