# Data formats

Formats for data that people produce and the code consumes. Each has a versioned schema name,
a loader and validator, and a synthetic example under [examples/](examples/) that the test
suite validates, so the documentation and the code cannot drift apart.

| Format | Schema | Owner | Used for |
|---|---|---|---|
| [Pairwise "which is harder?" judgements](pairwise-judgements.md) | `researchbridge.pairwise-judgements` v1 | Track R (`rbscores.human_data.pairwise`) | Validation 2 of the readability score |
| ["Terms I don't know" marks](term-marks.md) | `researchbridge.term-marks` v1 | Track R (`rbscores.human_data.marks`) | Validating the burden score; collected in Phase 1's comprehension study |

Every file carries `"synthetic": true` or `false`. Synthetic files (like the examples) exist for
tests and demos only and must never be reported, stored or seeded as real results. Raters are
identified only by pseudonyms.
