"""Validation 1: does each score rank the lay summary easier than the abstract?

For every article, the lay summary and the technical abstract are scored as
separate texts, and a metric "ranks the pair correctly" when the lay summary
gets the lower (easier) value. Reported per metric, per corpus and pooled:
the share of pairs ranked correctly with a 95% Wilson interval, ties, and a
two-sided sign test against 50%.

Why lay summary versus abstract: both are short summaries of the same paper
written for different readers, so topic, field and the paper's terminology
are held constant. Comparing against the full article would mostly measure
length and section mix (methods sections are hard in a way summaries never
are), and the full text is much longer, which affects every per-text rate.

Lengths still differ (eLife digests are longer than their abstracts; PLOS
author summaries are shorter), and the burden score counts each term once per
text, so a longer text has fewer new terms per word. Every comparison is
therefore repeated **length-matched**: the longer text is cut to whole
sentences so its word count is as close as possible to the shorter one's.

Metrics: the five readability features, the composite, the burden score, the
burden score with definition detection switched off (an ablation: does
removing defined terms help?), and the Flesch-Kincaid grade as a familiar
baseline that is not part of either score.

Two metrics are compared on the same pairs with an exact McNemar test (a sign
test on the pairs exactly one of them ranks correctly): the composite against
Flesch-Kincaid and against jargon density alone, and the burden score against
its no-definitions ablation (:data:`PAIRED_COMPARISONS`).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from spacy.language import Language

from rbscores.analysis import analyse_document
from rbscores.burden.score import BurdenParams
from rbscores.familiarity import Familiarity
from rbscores.readability.baseline import flesch_kincaid_grade
from rbscores.readability.composite import ReferenceStats
from rbscores.readability.features import FEATURE_NAMES, is_word
from rbscores.scoring import score_analysis, score_unit
from rbscores.stats import median, sign_test_p, spearman, wilson_interval
from rbscores.status import METHOD_VERSION, PROVISIONAL, PROVISIONAL_NOTICE
from rbscores.text import document_from_text
from rbscores.validation1.dataset import LayPair

METRICS: Final = (
    *FEATURE_NAMES,
    "composite",
    "burden",
    "burden_no_definitions",
    "flesch_kincaid_grade",
)
"""Every metric compared, each oriented so that lower means easier."""

COMPARISONS: Final = ("full", "length_matched")
PAIRED_COMPARISONS: Final = (
    ("composite", "flesch_kincaid_grade"),
    ("composite", "jargon_density"),
    ("burden", "burden_no_definitions"),
)
_MAX_EXAMPLES: Final = 10


@dataclass(frozen=True, slots=True)
class TextMetrics:
    """Every metric for one text.

    Attributes:
        words: Words in the text.
        values: Metric name to value (see :data:`METRICS`).
        z_scores: The composite's per-feature z-scores.
        undefined_terms: Undefined terms counted by the burden score.
        defined_terms: Terms removed because the text defines them.
    """

    words: int
    values: Mapping[str, float]
    z_scores: Mapping[str, float]
    undefined_terms: int
    defined_terms: int


@dataclass(frozen=True, slots=True)
class PairResult:
    """Both texts of one pair, measured in full and length-matched.

    Attributes:
        pair: The pair.
        lay: Lay summary, full.
        technical: Abstract, full.
        lay_matched: Lay summary, length-matched.
        technical_matched: Abstract, length-matched.
    """

    pair: LayPair
    lay: TextMetrics
    technical: TextMetrics
    lay_matched: TextMetrics
    technical_matched: TextMetrics

    def texts(self, comparison: str) -> tuple[TextMetrics, TextMetrics]:
        """Return the (lay, technical) metrics for a comparison.

        Args:
            comparison: "full" or "length_matched".

        Returns:
            The two texts' metrics.
        """
        if comparison == "full":
            return self.lay, self.technical
        return self.lay_matched, self.technical_matched


def measure_text(
    text: str, *, nlp: Language, familiarity: Familiarity, reference: ReferenceStats
) -> TextMetrics | None:
    """Score one text on every metric.

    Args:
        text: The text (blank lines separate paragraphs).
        nlp: spaCy pipeline with a parser.
        familiarity: Word-frequency source.
        reference: Reference statistics for the composite.

    Returns:
        The metrics, or None if the text has no words.
    """
    analysis = analyse_document(document_from_text(text), nlp=nlp, familiarity=familiarity)
    paper = score_analysis(analysis, reference=reference).paper
    if paper.readability is None or paper.composite is None or paper.z_scores is None:
        return None

    # The ablation: the same burden without removing defined terms.
    ablation = score_unit(
        analysis.paragraphs,
        level="paper",
        unit_id="paper",
        title=None,
        defined=analysis.defined,
        reference=reference,
        params=BurdenParams(use_definitions=False),
    )
    grade = flesch_kincaid_grade(s for a in analysis.paragraphs for s in a.sentence_words)
    values = {
        **paper.readability.values(),
        "composite": paper.composite,
        "burden": paper.burden.burden_per_1000,
        "burden_no_definitions": ablation.burden.burden_per_1000,
        "flesch_kincaid_grade": grade if grade is not None else 0.0,
    }
    return TextMetrics(
        words=paper.readability.words,
        values=values,
        z_scores=paper.z_scores,
        undefined_terms=len(paper.burden.undefined_terms),
        defined_terms=len(paper.burden.defined_terms),
    )


def truncate_to_words(text: str, target: int, *, nlp: Language) -> str:
    """Cut a text to whole sentences, as close as possible to a word count.

    Args:
        text: The text.
        target: Desired number of words.
        nlp: spaCy pipeline (for sentence boundaries and word counts).

    Returns:
        The first sentences whose word count is nearest ``target`` (at least
        one sentence), joined by spaces.
    """
    sentences = [s for s in nlp(text.replace("\n\n", " ")).sents if s.text.strip()]
    best_end, best_gap, words = 1, None, 0
    for end, sentence in enumerate(sentences, start=1):
        words += sum(1 for t in sentence if is_word(t))
        gap = abs(words - target)
        if best_gap is None or gap < best_gap:
            best_end, best_gap = end, gap
        if words >= target:
            break
    return " ".join(s.text.strip() for s in sentences[:best_end])


def evaluate_pair(
    pair: LayPair, *, nlp: Language, familiarity: Familiarity, reference: ReferenceStats
) -> PairResult | None:
    """Measure one pair in full and length-matched.

    Args:
        pair: The pair.
        nlp: spaCy pipeline with a parser.
        familiarity: Word-frequency source.
        reference: Reference statistics.

    Returns:
        The result, or None if either text has no words.
    """

    def measure(text: str) -> TextMetrics | None:
        """Measure one text with the shared settings."""
        return measure_text(text, nlp=nlp, familiarity=familiarity, reference=reference)

    lay = measure(pair.lay_summary)
    technical = measure(pair.abstract)
    if lay is None or technical is None:
        return None

    # Cut the longer text so both have about the same number of words.
    target = min(lay.words, technical.words)
    lay_matched, technical_matched = lay, technical
    if lay.words > target:
        lay_matched = measure(truncate_to_words(pair.lay_summary, target, nlp=nlp)) or lay
    if technical.words > target:
        technical_matched = measure(truncate_to_words(pair.abstract, target, nlp=nlp)) or technical
    return PairResult(pair, lay, technical, lay_matched, technical_matched)


def compare(results: Sequence[PairResult], metric: str, comparison: str) -> dict[str, Any]:
    """Summarise how often a metric ranks the lay summary easier.

    Args:
        results: Pair results.
        metric: Metric name.
        comparison: "full" or "length_matched".

    Returns:
        Counts, the share correct (ties count as incorrect) with its 95%
        Wilson interval, a sign test on the untied pairs, and medians.
    """
    correct = ties = 0
    lay_values: list[float] = []
    technical_values: list[float] = []
    for result in results:
        lay, technical = result.texts(comparison)
        lay_value, technical_value = lay.values[metric], technical.values[metric]
        lay_values.append(lay_value)
        technical_values.append(technical_value)
        if lay_value < technical_value:
            correct += 1
        elif lay_value == technical_value:
            ties += 1

    share = wilson_interval(correct, len(results))
    differences = [a - b for a, b in zip(lay_values, technical_values, strict=True)]
    return {
        "n": len(results),
        "lay_easier": correct,
        "ties": ties,
        "share_correct": share.value,
        "ci95_low": share.low,
        "ci95_high": share.high,
        "sign_test_p": sign_test_p(correct, len(results) - ties),
        "median_lay": median(lay_values),
        "median_technical": median(technical_values),
        "median_difference": median(differences),
    }


def paired_comparison(
    results: Sequence[PairResult], first: str, second: str, comparison: str
) -> dict[str, Any]:
    """Compare two metrics on the same pairs with an exact McNemar test.

    Args:
        results: Pair results.
        first: First metric.
        second: Second metric.
        comparison: "full" or "length_matched".

    Returns:
        How many pairs both, only the first, only the second, or neither rank
        correctly (ties count as incorrect), and the two-sided exact p-value
        on the discordant pairs.
    """
    counts = {"both": 0, "only_first": 0, "only_second": 0, "neither": 0}
    for result in results:
        lay, technical = result.texts(comparison)
        first_right = lay.values[first] < technical.values[first]
        second_right = lay.values[second] < technical.values[second]
        if first_right and second_right:
            counts["both"] += 1
        elif first_right:
            counts["only_first"] += 1
        elif second_right:
            counts["only_second"] += 1
        else:
            counts["neither"] += 1
    discordant = counts["only_first"] + counts["only_second"]
    return {
        "first": first,
        "second": second,
        **counts,
        "mcnemar_exact_p": sign_test_p(counts["only_first"], discordant),
    }


def failure_analysis(results: Sequence[PairResult]) -> dict[str, Any]:
    """Describe the pairs the composite gets wrong (full comparison).

    Args:
        results: Pair results.

    Returns:
        Failure count, which features push failures towards "lay is harder"
        (median z-score difference per feature among failures), how many
        failures also fail on burden, length effects, and the worst examples.
    """
    failures = [r for r in results if r.lay.values["composite"] >= r.technical.values["composite"]]

    # Which features drive the failures: lay minus technical z-scores.
    feature_shift = {
        name: median([r.lay.z_scores[name] - r.technical.z_scores[name] for r in failures])
        for name in FEATURE_NAMES
    }

    # Is getting it wrong related to the lay text being relatively long?
    ratios = [r.lay.words / r.technical.words for r in results]
    composite_gap = [r.lay.values["composite"] - r.technical.values["composite"] for r in results]

    worst = sorted(
        failures,
        key=lambda r: r.lay.values["composite"] - r.technical.values["composite"],
        reverse=True,
    )[:_MAX_EXAMPLES]
    return {
        "composite_failures": len(failures),
        "of_pairs": len(results),
        "median_feature_z_difference_in_failures": feature_shift,
        "failures_also_failing_burden": sum(
            1 for r in failures if r.lay.values["burden"] >= r.technical.values["burden"]
        ),
        "failures_with_longer_lay_text": sum(
            1 for r in failures if r.lay.words > r.technical.words
        ),
        "spearman_length_ratio_vs_composite_gap": spearman(ratios, composite_gap),
        "worst_examples": [_example(r) for r in worst],
    }


def _example(result: PairResult) -> dict[str, Any]:
    """Summarise one failing pair for the report.

    Args:
        result: A pair result.

    Returns:
        ID, title, year, word counts, composites and per-feature z differences.
    """
    return {
        "id": result.pair.id,
        "title": result.pair.title,
        "year": result.pair.year,
        "lay_words": result.lay.words,
        "technical_words": result.technical.words,
        "lay_composite": result.lay.values["composite"],
        "technical_composite": result.technical.values["composite"],
        "z_difference": {
            name: result.lay.z_scores[name] - result.technical.z_scores[name]
            for name in FEATURE_NAMES
        },
    }


def summarise(
    results: Sequence[PairResult],
    *,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the full validation 1 results document.

    Args:
        results: Every pair result.
        metadata: Provenance to record (dataset revisions, model, reference).

    Returns:
        A JSON-serialisable mapping: provisional notice, metadata, per-source
        and pooled comparisons for every metric, paired metric comparisons,
        median word and term counts, and the failure analysis.
    """
    groups = _groups(results)
    return {
        "provisional": PROVISIONAL,
        "notice": PROVISIONAL_NOTICE,
        "method_version": METHOD_VERSION,
        **metadata,
        "pairs": {name: len(items) for name, items in groups.items()},
        "comparisons": {
            comparison: {
                name: {metric: compare(items, metric, comparison) for metric in METRICS}
                for name, items in groups.items()
            }
            for comparison in COMPARISONS
        },
        "paired": {
            comparison: {
                name: [paired_comparison(items, a, b, comparison) for a, b in PAIRED_COMPARISONS]
                for name, items in groups.items()
            }
            for comparison in COMPARISONS
        },
        "words": {
            name: {
                "lay_median": median([float(r.lay.words) for r in items]),
                "technical_median": median([float(r.technical.words) for r in items]),
                "matched_lay_median": median([float(r.lay_matched.words) for r in items]),
                "matched_technical_median": median(
                    [float(r.technical_matched.words) for r in items]
                ),
            }
            for name, items in groups.items()
        },
        "terms": {
            name: {
                "lay_undefined": median([float(r.lay.undefined_terms) for r in items]),
                "technical_undefined": median([float(r.technical.undefined_terms) for r in items]),
                "lay_defined": median([float(r.lay.defined_terms) for r in items]),
                "technical_defined": median([float(r.technical.defined_terms) for r in items]),
            }
            for name, items in groups.items()
        },
        "failure_analysis": {name: failure_analysis(items) for name, items in groups.items()},
    }


def _groups(results: Sequence[PairResult]) -> dict[str, list[PairResult]]:
    """Split results by corpus and add a pooled group.

    Args:
        results: Every pair result.

    Returns:
        ``{"elife": [...], "plos": [...], "all": [...]}`` (only sources present).
    """
    groups: dict[str, list[PairResult]] = {}
    for result in results:
        groups.setdefault(result.pair.source, []).append(result)
    groups["all"] = list(results)
    return groups


def evaluate_pairs(
    pairs: Iterable[LayPair],
    *,
    nlp: Language,
    familiarity: Familiarity,
    reference: ReferenceStats,
    progress: Callable[[int], None] | None = None,
) -> tuple[list[PairResult], list[str]]:
    """Measure many pairs.

    Args:
        pairs: The pairs.
        nlp: spaCy pipeline with a parser.
        familiarity: Word-frequency source.
        reference: Reference statistics.
        progress: Called with the number of pairs done after each pair.

    Returns:
        The results and the IDs of pairs skipped because a text had no words.
    """
    results: list[PairResult] = []
    skipped: list[str] = []
    for done, pair in enumerate(pairs, start=1):
        result = evaluate_pair(pair, nlp=nlp, familiarity=familiarity, reference=reference)
        if result is None:
            skipped.append(pair.id)
        else:
            results.append(result)
        if progress is not None:
            progress(done)
    return results, skipped
