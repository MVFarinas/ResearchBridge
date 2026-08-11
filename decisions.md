# Decisions — ResearchBridge

Locked scope and architecture choices, and the questions still genuinely open. When this file
conflicts with [inspiration.md](inspiration.md), **this file wins** — inspiration.md is the
original brain-dump and is kept as background, not as spec.

Format: numbered, dated, with the alternatives considered. A decision that invalidates an earlier
one supersedes it in writing rather than editing it away.

---

## 1. Locked

### 1.1 Licence-gated corpus — the keystone safety decision (2026-08-10)

**Only ingest papers whose licence permits what we do to them, and store the licence per paper.**

Every core feature is reproduction. The rewriting feature produces a **derivative work** of the
full paper; the inline-explanation feature **displays the original in full**. Only the summary
engine is comfortably safe, since facts are not copyrightable. Feature 2 is the exposed one, and
it is also the one the project treats as most important, because it is what preserves scientific
integrity.

**"Open access" is not one thing, and this is the part that bites.** CC-BY permits derivative
works with attribution. **CC-BY-ND explicitly forbids them**, and a plain-English rewrite is
squarely a derivative. So the rule is not "open access only":

| Licence | Display original | Rewrite (derivative) |
|---|---|---|
| CC-BY, CC-BY-SA | yes | yes, with attribution |
| CC-BY-ND | yes | **no** |
| CC-BY-NC variants | yes | yes, but constrains commercialisation later |
| All rights reserved / paywalled | **no** | **no** |

**Decision:** store a `licence` field per paper at ingestion and gate features on it. Rewriting
requires derivative permission. Never ingest paywalled or all-rights-reserved content.

**Why this is not a painful compromise.** arXiv, PubMed Central, PLOS and DOAJ are millions of
papers, most under CC-BY. The audience named in inspiration.md — general public, students,
journalists, people checking a claim they saw online — largely cannot reach paywalled papers
anyway, so the excluded corpus is one they could not use. And the rule is *checkable*: a licence
field either grants derivative rights or it does not, with no per-paper judgement call.

**Consequences.** The ingestion schema needs the licence field from day one; retrofitting it once
a corpus exists means re-deriving provenance for everything already stored. Attribution and licence
display become UI requirements, not nice-to-haves. If a paid tier is ever considered, the NC
variants have to be re-examined, because non-commercial terms and a subscription do not mix.

**Alternatives rejected:** ingest anything and rely on fair use or fair dealing (unpredictable
across jurisdictions, and weakest for exactly the full-text-display case we need); link out to the
publisher rather than display (kills feature 2, which is the differentiator); ask publishers for
permission (does not scale for a solo project, and blocks the build on other people's legal teams).

---

## 2. Open — need a decision before build

### 2.1 Annotation model ⚠️ this one decides what company this is

How do readers get explanations of difficult passages? inspiration.md offers two and says they
"may coexist."

- **(a) Community annotation**, Genius-style. Humans explain passages for each other.
- **(b) LLM annotation.** Generated explanations, no community required.

These are **different products with different cost structures**, not a feature toggle. (a) means
cold-start problems, moderation, and network effects, with a quality ceiling set by the crowd; it
is defensible once it works because the annotations are a moat. (b) ships alone on day one with a
quality ceiling set by the model, and inherits every faithfulness risk in §2.2; it is also
trivially copyable.

A hybrid inherits **both** cost structures, so "they may coexist" is the option needing the most
scrutiny, not the safe middle. **Pending.**

### 2.2 Faithfulness measurement — how do we know a rewrite is honest?

The stated design philosophy is to preserve scientific integrity and never turn nuance into
clickbait. That is not a philosophy question, it is a **measurable** one: a rewrite that introduces
a claim the source does not support is a grounding failure.

This is the same problem, and the same metric, as the Groundedness scoring in
[the JAMN Bot study](https://github.com/JAMNSoftware/jamn-rag-benchmark) — score generated text
against the source passage on a rubric, with human raters setting the reference and inter-rater
agreement establishing credibility. A small benchmark of a few dozen passages would de-risk the
core feature before any product work, and would settle §2.1 with evidence rather than preference.

**Pending** — but this is the cheapest high-value thing available and should probably come first.

### 2.3 Credibility scoring is a claim about other people's work

inspiration.md proposes journal-quality signals, including distinguishing respected journals from
predatory ones. Publishing a low-quality label about a named journal in a shipped product is a
materially different risk surface from summarizing a paper. Options: use only neutral quantitative
signals (citation count, recency), defer to an external list and attribute it, or drop the feature.
**Pending.**

### 2.4 The two invented metrics need definitions before they need code

The **readability/convolution score** and the **prior-knowledge burden score** are the original
contributions in inspiration.md, and both are currently vibes. Either could be a small publishable
result on its own. Neither can be built until it is defined and validated against human judgement.
**Pending.**

---

## 3. Not decided, not yet needed

Stack, hosting, and form factor are untouched. There is no code yet and nothing here constrains
them, except that §1.1 requires a licence field wherever papers are stored.
