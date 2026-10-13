# Lay comprehension study: scaffold

**Status: scaffold only. No questions have been written, no participants recruited.**

Plan.md Phase 1 ("Comprehension study") and decisions.md §1.3/§1.4: lay readers answer questions
about the same passages after reading them in one of three arms, so that comprehension can be
compared between the **original** passage, the **LLM rewrite**, and a **human rewrite**. Lay
raters are for comprehension, never for faithfulness (§1.4).

## Files

| File | What |
|---|---|
| [schema_v1.json](schema_v1.json) | JSON Schema (draft 2020-12) for a question set: study, ethics status, arms, design, passages and questions. |
| [template_v1.yaml](template_v1.yaml) | An empty template that validates against the schema. Copy it to start. |

Validate a question set with `rbbench comprehension validate <file>`. Status `TEMPLATE` and `DRAFT`
may have no questions; `FINAL` needs at least one question per passage **and** an ethics status of
`approved` or `not_required`, so a set cannot be finalised before the ethics question is answered.

## Design choices encoded in the schema (proposals for the owner)

- **Arms** are fixed: `original`, `llm_rewrite`, `human_rewrite`. The human arm's texts do not exist
  yet (pending: a person writes them, Plan.md "Human-written arm").
- **Allocation** defaults to within-subjects with a Latin square: each participant reads every
  passage once, each in a different arm, so arm and passage effects can be separated with few
  participants. Between-subjects is allowed.
- **Question targets** mirror the faithfulness rubric's failure modes (`main_finding`,
  `population`, `number`, `certainty`, `causal_claim`, `limitation`, `recommendation`), so
  comprehension failures can be related to faithfulness failures in the same passage.
- Every question must be **answerable from all three arms**; the `rationale` field records where
  the original passage states the answer.

## "Terms I don't know" marking

Lay readers will also mark the terms they do not know (the validation data for the prior-knowledge
burden score, decisions.md §2.4). That data format is **defined by Track R (scores/)**; this study
only records, under `jargon_marking`, that it is collected.

## Before recruiting anyone

- **Research ethics.** The owner should check whether **University of Alberta** research-ethics
  approval is needed before recruiting lay readers (and the domain-literate faithfulness raters),
  and record the outcome under `study.ethics`. This scaffold does not presume either answer.
- Consent wording, payment, data retention and anonymisation are not covered here and need the
  same check.
