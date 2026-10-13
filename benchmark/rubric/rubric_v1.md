# Faithfulness rubric, version 1

> **DRAFT, for the owner's review (2026-10-13).** Not yet piloted with raters or used by the judge
> on real rewrites. The machine-readable version is [rubric_v1.yaml](rubric_v1.yaml); if the two
> ever differ, the YAML is what the tools use and this page must be fixed. How to apply each code,
> with worked examples: [rater_guide_v1.md](rater_guide_v1.md).

## What is being rated

A rewrite is a plain-English version of a short passage (a few paragraphs) of a paper. It is
**paragraph-aligned**: each rewritten paragraph corresponds to exactly one source paragraph. The
model may add at most one or two sentences of context per paragraph, but must mark each addition,
so additions are classified here rather than forbidden.

Each rewritten paragraph is split into **atomic claims** (one checkable statement each). Raters
see each claim next to its source paragraph, with the whole source passage available for context.

Two units are rated:

| Unit | What | Codes |
|---|---|---|
| claim | one atomic claim from a rewritten paragraph | all codes except `dropped_limitation` |
| paragraph | one rewritten paragraph as a whole | `dropped_limitation` |

## Why separate binary codes

decisions.md §1.4: narrow yes/no checks agree far better than one overall faithfulness rating
(Cohen's κ 0.79–0.95 for Peters & Chin-Yee's coding, against Krippendorff's α 0.20–0.64 for
holistic crowd ratings in Devaraj et al. 2022). So every failure mode is its own code, each code is
judged independently, and agreement is reported per code.

Codes never depend on each other. A claim can be `supported` and still have a `lost_hedge` (the
facts are right but stated with more certainty). A claim taken from a marked addition is usually
`unsupported` (the source does not say it) and is then classified by `added_information`.

## Claim-level codes

| Code | Values | Question |
|---|---|---|
| `support` | supported / unsupported / contradicted | Does the source passage support this claim? |
| `overgen_generic` | no / yes | Does the claim turn a quantified or qualified statement about the studied sample into a generic statement? |
| `overgen_present_tense` | no / yes | Does the claim turn a past-tense report of what was found into a present-tense general truth? |
| `overgen_action_guiding` | no / yes | Does the claim turn a description of a finding into a recommendation or a statement about what people should do? |
| `lost_hedge` | no / yes | Is the claim more certain than the source? |
| `correlation_to_causation` | no / yes | Does the claim present an association from the source as cause and effect? |
| `spin` | no / yes | Does the claim make the finding look more favourable, important or conclusive than the source reports? |
| `substituted_detail` | no / yes | Does the claim change a number, unit, population, intervention, comparator or outcome from the source? |
| `added_information` | no / factual / non_factual | Does the claim add information that is not in the source passage, and if so, is it correct? |

### `support`

- **supported**: the source states the claim or directly entails it. Simplified wording counts if
  a domain expert would accept it as saying the same thing.
- **unsupported**: the source neither states nor entails the claim, and does not contradict it.
  Added background, marked or not, is usually here.
- **contradicted**: the source says something incompatible with the claim (a different direction
  of effect, number, population, conclusion or certainty that cannot both be true).

### Overgeneralisation: three shifts (Peters & Chin-Yee 2025)

Peters & Chin-Yee (R Soc Open Sci 2025, doi:10.1098/rsos.241776) coded overgeneralisation in
4,900 LLM summaries as three transitions, with Cohen's κ 0.79–0.95. Each is a separate code here:

- `overgen_generic`: **quantified to generic**. The source limits a finding ("in 62% of the mice
  tested", "in this cohort of older adults"); the claim drops the limit ("mice", "people").
- `overgen_present_tense`: **past to present tense**. The source reports what was found ("reduced
  symptoms"); the claim states a timeless fact ("reduces symptoms"). Tense about the paper itself
  ("the authors show") does not count.
- `overgen_action_guiding`: **descriptive to action-guiding**. The source describes; the claim
  tells someone what to do or what is safe or effective for them.

`overgeneralisation` is **derived**: yes if any of the three is yes. It is computed, never rated
directly, and its agreement is reported alongside the three shifts.

### `lost_hedge`

Yes when the source hedges ("may", "suggests", "is associated with", "preliminary", "we
speculate") or reports uncertainty ("not statistically significant", wide intervals, "could not
determine") and the claim drops the hedge or is more certain. No when an equivalent hedge is kept
or the source is itself certain.

### `correlation_to_causation`

Yes when the source reports an association (observational data, "linked to", "associated with")
and the claim uses causal language ("causes", "leads to", "prevents", "because of"). No when the
claim stays correlational, or the source supports a causal statement (a randomised comparison or
a direct experimental manipulation that the authors describe causally). After Yu, Li & Wang
(EMNLP-IJCNLP 2019) and Yu, Wang & Li (COLING 2020).

### `spin`

Yes when the claim adds favourable framing the source does not give: a non-significant or
secondary result presented as a success, a benefit stressed while the reported harm or null
primary outcome is left out, "breakthrough", "proof", "cure", or overstated importance. Spin that
is already in the source and carried over faithfully is **not** coded (note it in the comment).
After Boutron & Ravaud (PNAS 2018).

### `substituted_detail`

Yes when any reported quantity differs (including rounding that changes the meaning, a relative
risk stated as absolute, a wrong unit), or the claim names a different population, species,
intervention, comparator or outcome (the PICO elements, as in FactPICO). After Devaraj et al.
(ACL 2022) substitution errors.

### `added_information`

- **no**: the claim's content comes from the source passage.
- **factual**: the claim adds information beyond the source (background, a definition, context)
  that is correct as general knowledge and does not change what the paper found.
- **non_factual**: the added information is wrong, unverifiable, or presented as if the paper
  found it.

Rate this for every claim, marked or not: an unmarked addition is the failure the marking rule is
there to catch. The packet shows whether the claim came from a marked addition. After FactPICO's
added-information labels (Joseph et al., ACL 2024).

## Paragraph-level code

| Code | Values | Question |
|---|---|---|
| `dropped_limitation` | no / yes | Does the rewritten paragraph leave out a limitation, caveat or uncertainty that its source paragraph states? |

Yes when the source paragraph states a limitation (sample size, design, generalisability,
confounding, preliminary nature, an unexplained or contrary result) and the rewritten paragraph
does not convey it. Omissions are a property of the whole paragraph, not of any one claim, which
is why this code is rated per paragraph.

## How results are reported

For every code, rated and derived: the number of units, the value distribution (prevalence), the
pooled observed agreement, Cohen's κ (two raters; the mean over pairs for more), Fleiss' κ and
Krippendorff's α (nominal). A κ or α is reported as undefined, not as a number, when a code shows
no variation. Disagreements are adjudicated and the adjudicated labels are the benchmark result.

## Open questions for the owner

1. Should `support` judge against the aligned source paragraph only, or the whole passage (the
   current draft allows the whole passage, since a rewrite may reasonably merge context)?
2. Is `spin` distinct enough from `lost_hedge` and the overgeneralisation shifts to be rated
   reliably? A calibration round on the first rewrite will show it.
3. Should a factual marked addition count against a rewrite at all? The draft records it and leaves
   the policy to the gate threshold, which Phase 1 decides.
