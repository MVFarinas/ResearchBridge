"""Human-study data formats owned by Track R, with loaders, validators and evaluation.

* :mod:`~rbscores.human_data.pairwise`: lay readers' "which is harder?"
  judgements (validation 2 of the readability score).
* :mod:`~rbscores.human_data.marks`: lay readers' "terms I don't know" marks
  (validation of the burden score; collected in Phase 1's comprehension study).

The formats are specified in docs/data-formats/. No real human data exists
yet; the tests use small synthetic studies, flagged ``"synthetic": true``.
"""
