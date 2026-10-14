"""Validation 2 data: lay readers' pairwise "which is harder?" judgements.

Format: docs/data-formats/pairwise-judgements.md (schema
``researchbridge.pairwise-judgements``, version 1). Each judgement records
one rater's answer for one pair of passages: ``"a"`` (the first passage is
harder), ``"b"``, or ``"same"``.

Evaluation (:func:`evaluate_pairwise`): for each metric, the share of
decisive judgements (not "same") where the metric gives the harder passage
the higher value, with a 95% Wilson interval; the same share over passage
pairs with a strict majority verdict; and, as a ceiling, how often two raters
agree on the same pair. A metric tie counts as a disagreement.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Final

from spacy.language import Language

from rbscores.familiarity import Familiarity, WordfreqFamiliarity
from rbscores.human_data.common import HumanDataError, StudyHeader, parse_header, read_json
from rbscores.nlp import load_pipeline
from rbscores.readability.composite import ReferenceStats, load_reference
from rbscores.readability.features import FEATURE_NAMES
from rbscores.scoring import score_document
from rbscores.stats import wilson_interval
from rbscores.text import single_paragraph_document

SCHEMA: Final = "researchbridge.pairwise-judgements"
VERDICTS: Final = ("a", "b", "same")
SCORE_METRICS: Final = (*FEATURE_NAMES, "composite", "burden")


@dataclass(frozen=True, slots=True)
class Judgement:
    """One rater's verdict on one pair.

    Attributes:
        rater_id: The rater.
        passage_a: First passage ID.
        passage_b: Second passage ID.
        harder: "a", "b" or "same".
        shown_first: Which passage was displayed first ("a" or "b"), if recorded.
    """

    rater_id: str
    passage_a: str
    passage_b: str
    harder: str
    shown_first: str | None = None

    @property
    def pair_key(self) -> tuple[str, str]:
        """The unordered pair as a sorted tuple."""
        a, b = sorted((self.passage_a, self.passage_b))
        return a, b

    @property
    def harder_passage(self) -> str | None:
        """The passage judged harder, or None for "same"."""
        if self.harder == "a":
            return self.passage_a
        if self.harder == "b":
            return self.passage_b
        return None


@dataclass(frozen=True, slots=True)
class PairwiseStudy:
    """A validated pairwise-judgement study.

    Attributes:
        header: Study ID, synthetic flag, passages and raters.
        judgements: Every judgement, in file order.
    """

    header: StudyHeader
    judgements: tuple[Judgement, ...]

    def summary(self) -> str:
        """Describe the study in one line.

        Returns:
            Counts of passages, raters and judgements, flagged if synthetic.
        """
        flag = " [SYNTHETIC]" if self.header.synthetic else ""
        return (
            f"study {self.header.study_id}{flag}: {len(self.header.passages)} passages, "
            f"{len(self.header.raters)} raters, {len(self.judgements)} judgements"
        )


def parse_pairwise(data: Any) -> PairwiseStudy:
    """Validate and parse a pairwise-judgement document.

    Args:
        data: Parsed JSON.

    Returns:
        The study.

    Raises:
        HumanDataError: Listing every problem, if the document is invalid.
    """
    problems: list[str] = []
    header = parse_header(data, SCHEMA, problems)
    judgements: list[Judgement] = []
    if header is not None:
        judgements = _parse_judgements(data.get("judgements"), header, problems)
    if problems or header is None:
        raise HumanDataError(problems)
    return PairwiseStudy(header=header, judgements=tuple(judgements))


def load_pairwise(path: str | Path) -> PairwiseStudy:
    """Load and validate a pairwise-judgement file.

    Args:
        path: JSON file.

    Returns:
        The study.

    Raises:
        HumanDataError: If the file is unreadable or invalid.
    """
    return parse_pairwise(read_json(path))


def _parse_judgements(items: Any, header: StudyHeader, problems: list[str]) -> list[Judgement]:
    """Check and parse the ``judgements`` list.

    Args:
        items: The raw value.
        header: The parsed header (for referential checks).
        problems: List to append problems to.

    Returns:
        Valid judgements.
    """
    if not isinstance(items, list) or not items:
        problems.append("'judgements' must be a non-empty list")
        return []
    judgements: list[Judgement] = []
    seen: set[tuple[str, tuple[str, str]]] = set()
    for index, item in enumerate(items):
        where = f"judgements[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue

        # References, verdict and display order.
        rater, first, second = item.get("rater_id"), item.get("passage_a"), item.get("passage_b")
        harder, shown = item.get("harder"), item.get("shown_first")
        # IDs must be strings before the membership tests (a list is unhashable).
        errors = []
        if not isinstance(rater, str) or rater not in header.raters:
            errors.append(f"{where}.rater_id {rater!r} is not a listed rater")
        for name, value in (("passage_a", first), ("passage_b", second)):
            if not isinstance(value, str) or value not in header.passages:
                errors.append(f"{where}.{name} {value!r} is not a listed passage")
        if first == second:
            errors.append(f"{where} compares a passage with itself")
        if harder not in VERDICTS:
            errors.append(f"{where}.harder must be one of {', '.join(VERDICTS)}")
        if shown is not None and shown not in ("a", "b"):
            errors.append(f"{where}.shown_first must be 'a' or 'b' if given")
        if errors:
            problems.extend(errors)
            continue

        # One verdict per rater per unordered pair.
        judgement = Judgement(str(rater), str(first), str(second), str(harder), shown)
        key = (judgement.rater_id, judgement.pair_key)
        if key in seen:
            problems.append(f"{where} repeats rater {rater!r} on the same pair")
            continue
        seen.add(key)
        judgements.append(judgement)
    return judgements


def evaluate_pairwise(
    study: PairwiseStudy, scores: Mapping[str, Mapping[str, float]]
) -> dict[str, Any]:
    """Score metrics against the human judgements.

    Args:
        study: The study.
        scores: ``scores[metric][passage_id]`` = the metric's value, higher
            meaning harder. Every passage in a judgement needs a value.

    Returns:
        Counts, the inter-rater agreement ceiling, and per metric the
        judgement-level and majority-level agreement with 95% intervals.

    Raises:
        KeyError: If a judged passage has no value for a metric.
    """
    decisive = [j for j in study.judgements if j.harder != "same"]
    majorities = _majority_verdicts(study.judgements)
    metrics: dict[str, Any] = {}
    for metric, values in scores.items():
        # Judgement level: does the metric put the judged-harder passage higher?
        hits = sum(1 for j in decisive if _agrees(j, values))
        judgement_share = wilson_interval(hits, len(decisive))

        # Pair level: agreement with each pair's strict-majority verdict.
        majority_hits = sum(
            1
            for (a, b), harder in majorities.items()
            if values[harder] > values[b if harder == a else a]
        )
        majority_share = wilson_interval(majority_hits, len(majorities))
        metrics[metric] = {
            "judgement_agreement": judgement_share.value,
            "judgement_ci95": [judgement_share.low, judgement_share.high],
            "majority_agreement": majority_share.value,
            "majority_ci95": [majority_share.low, majority_share.high],
        }
    return {
        "study_id": study.header.study_id,
        "synthetic": study.header.synthetic,
        "judgements": len(study.judgements),
        "decisive_judgements": len(decisive),
        "pairs": len({j.pair_key for j in study.judgements}),
        "pairs_with_majority": len(majorities),
        "rater_agreement": rater_agreement(study.judgements),
        "metrics": metrics,
    }


def _agrees(judgement: Judgement, values: Mapping[str, float]) -> bool:
    """Check whether a metric agrees with one decisive judgement.

    Args:
        judgement: A judgement with verdict "a" or "b".
        values: Metric values by passage ID.

    Returns:
        True if the harder passage has the strictly higher value.
    """
    harder = judgement.harder_passage
    easier = judgement.passage_b if harder == judgement.passage_a else judgement.passage_a
    return harder is not None and values[harder] > values[easier]


def _majority_verdicts(judgements: tuple[Judgement, ...]) -> dict[tuple[str, str], str]:
    """Find each pair's strict-majority "harder" passage, ignoring "same".

    Args:
        judgements: Every judgement.

    Returns:
        Pair key to the passage most raters judged harder; pairs with a tie
        or only "same" verdicts are left out.
    """
    votes: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for judgement in judgements:
        harder = judgement.harder_passage
        if harder is not None:
            votes[judgement.pair_key][harder] += 1
    majorities: dict[tuple[str, str], str] = {}
    for key, counts in votes.items():
        ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            majorities[key] = ranked[0][0]
    return majorities


def rater_agreement(judgements: tuple[Judgement, ...]) -> dict[str, Any]:
    """Measure how often two raters give the same verdict on the same pair.

    Verdicts are compared as "which passage is harder, or same", so "a" from
    one rater and "b" from another agree when the passages were listed in
    opposite orders.

    Args:
        judgements: Every judgement.

    Returns:
        The number of pairs judged by two or more raters and the share of
        agreeing rater-pairs over them (None if there are none).
    """
    by_pair: dict[tuple[str, str], list[str]] = defaultdict(list)
    for judgement in judgements:
        by_pair[judgement.pair_key].append(judgement.harder_passage or "same")
    agree = total = 0
    shared = [verdicts for verdicts in by_pair.values() if len(verdicts) > 1]
    for verdicts in shared:
        for first, second in combinations(verdicts, 2):
            total += 1
            agree += first == second
    return {
        "pairs_with_multiple_raters": len(shared),
        "rater_pair_agreement": agree / total if total else None,
    }


def score_passages(
    study: PairwiseStudy,
    *,
    nlp: Language | None = None,
    familiarity: Familiarity | None = None,
    reference: ReferenceStats | None = None,
) -> dict[str, dict[str, float]]:
    """Compute every PROVISIONAL metric for every passage in a study.

    Args:
        study: The study.
        nlp: spaCy pipeline (default: the configured one).
        familiarity: Word-frequency source (default: wordfreq).
        reference: Reference statistics (default: packaged).

    Returns:
        ``values[metric][passage_id]`` for :data:`SCORE_METRICS`; a passage
        without words gets 0 for every metric.
    """
    pipeline = nlp or load_pipeline()
    lookup = familiarity or WordfreqFamiliarity()
    ref = reference or load_reference()
    values: dict[str, dict[str, float]] = {metric: {} for metric in SCORE_METRICS}
    for passage_id, passage in study.header.passages.items():
        document = single_paragraph_document(passage.text, paragraph_id=passage_id)
        paper = score_document(document, nlp=pipeline, familiarity=lookup, reference=ref).paper
        features = paper.readability.values() if paper.readability else {}
        for name in FEATURE_NAMES:
            values[name][passage_id] = features.get(name, 0.0)
        values["composite"][passage_id] = paper.composite or 0.0
        values["burden"][passage_id] = paper.burden.burden_per_1000
    return values


def evaluate_pairwise_with_scores(study: PairwiseStudy) -> dict[str, Any]:
    """Score every passage with the PROVISIONAL metrics and evaluate them.

    Args:
        study: The study.

    Returns:
        The output of :func:`evaluate_pairwise`.
    """
    return evaluate_pairwise(study, score_passages(study))
