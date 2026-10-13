"""ResearchBridge faithfulness benchmark (decisions.md §1.4).

Subpackages and modules, one per benchmark step:
    rbbench.selection: candidate shortlist from PubMed and the PMC Cloud Service.
    rbbench.ingest: JATS download, parsing into paragraph units, passage proposal.
    rbbench.rewrite: paragraph-aligned rewrite harness with marked additions.
    rbbench.claims: claim decomposition (LLM prompt and sentence fallback).
    rbbench.rubric: the machine-readable rubric.
    rbbench.packets: offline rater packets and the ratings importer.
    rbbench.agreement: Cohen's kappa, Fleiss' kappa, Krippendorff's alpha, adjudication.
    rbbench.judge: LLM judge harness and FactPICO calibration.
    rbbench.baselines: optional automatic metrics (AlignScore, MiniCheck, QAFactEval).
    rbbench.comprehension: lay comprehension study schema validation.
    rbbench.dryrun: the end-to-end synthetic dry run.
"""

__version__ = "0.1.0"
