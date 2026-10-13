"""Burden validation data: lay readers' "terms I don't know" marks.

Format: docs/data-formats/term-marks.md (schema ``researchbridge.term-marks``,
version 1). Each response is one rater's marks on one passage, as character
spans of the exact passage text. A response with no marks means the rater
read the passage and knew every term; a passage a rater never saw has no
response from them. Phase 1's comprehension study collects these marks.

Evaluation (:func:`evaluate_marks`) asks whether the burden pipeline tracks
what readers mark:

* **Term level.** Each candidate term in a passage gets a *mark rate*: the
  share of the passage's respondents whose marks overlap the term. The
  term's burden weight (0 if the passage defines it) should rise with the
  mark rate: Spearman correlation, and the AUC of weight for telling terms
  most respondents marked (rate >= 0.5) from the rest.
* **List quality.** Precision of the undefined, unfamiliar term list (weight
  > 0) against terms marked by anyone and by most; recall of readers' marks
  by that list and by all candidate terms.
* **Passage level.** Spearman correlation between the burden score and the
  mean number of marks per 1,000 words.

Familiarity varies a lot between readers (August et al.), so agreement is a
population-level check, not a per-reader one.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

from spacy.language import Language

from rbscores.analysis import analyse_document
from rbscores.burden.references import overlaps_any
from rbscores.burden.score import LocatedTerm, compute_burden
from rbscores.familiarity import Familiarity, WordfreqFamiliarity
from rbscores.human_data.common import HumanDataError, StudyHeader, parse_header, read_json
from rbscores.nlp import load_pipeline
from rbscores.stats import auc, spearman
from rbscores.text import single_paragraph_document

SCHEMA: Final = "researchbridge.term-marks"
MAJORITY: Final = 0.5
"""A term is "marked by most" when at least this share of respondents marked it."""


@dataclass(frozen=True, slots=True)
class Mark:
    """One span a rater marked as unknown.

    Attributes:
        start: Character offset in the passage text.
        end: End offset (exclusive).
        text: The marked text, equal to ``passage.text[start:end]``.
    """

    start: int
    end: int
    text: str


@dataclass(frozen=True, slots=True)
class Response:
    """One rater's marks on one passage.

    Attributes:
        rater_id: The rater.
        passage_id: The passage.
        marks: Marked spans, sorted, not overlapping (may be empty).
    """

    rater_id: str
    passage_id: str
    marks: tuple[Mark, ...]


@dataclass(frozen=True, slots=True)
class MarksStudy:
    """A validated term-marks study.

    Attributes:
        header: Study ID, synthetic flag, passages and raters.
        responses: Every response, in file order.
    """

    header: StudyHeader
    responses: tuple[Response, ...]

    def summary(self) -> str:
        """Describe the study in one line.

        Returns:
            Counts of passages, raters, responses and marks, flagged if synthetic.
        """
        flag = " [SYNTHETIC]" if self.header.synthetic else ""
        marks = sum(len(r.marks) for r in self.responses)
        return (
            f"study {self.header.study_id}{flag}: {len(self.header.passages)} passages, "
            f"{len(self.header.raters)} raters, {len(self.responses)} responses, {marks} marks"
        )


@dataclass(frozen=True, slots=True)
class PassageTerm:
    """A candidate term in a passage, as the burden pipeline sees it.

    Attributes:
        key: Term key.
        weight: Burden weight (0 if familiar or defined in the passage).
        spans: Character spans of its occurrences.
    """

    key: str
    weight: float
    spans: tuple[tuple[int, int], ...]


@dataclass(frozen=True, slots=True)
class PassageTerms:
    """The burden pipeline's view of one passage.

    Attributes:
        passage_id: The passage.
        words: Words in the passage.
        burden_per_1000: The PROVISIONAL burden score.
        terms: Every candidate term.
    """

    passage_id: str
    words: int
    burden_per_1000: float
    terms: tuple[PassageTerm, ...]


def parse_marks(data: Any) -> MarksStudy:
    """Validate and parse a term-marks document.

    Args:
        data: Parsed JSON.

    Returns:
        The study.

    Raises:
        HumanDataError: Listing every problem, if the document is invalid.
    """
    problems: list[str] = []
    header = parse_header(data, SCHEMA, problems)
    responses: list[Response] = []
    if header is not None:
        responses = _parse_responses(data.get("responses"), header, problems)
    if problems or header is None:
        raise HumanDataError(problems)
    return MarksStudy(header=header, responses=tuple(responses))


def load_marks(path: str | Path) -> MarksStudy:
    """Load and validate a term-marks file.

    Args:
        path: JSON file.

    Returns:
        The study.

    Raises:
        HumanDataError: If the file is unreadable or invalid.
    """
    return parse_marks(read_json(path))


def _parse_responses(items: Any, header: StudyHeader, problems: list[str]) -> list[Response]:
    """Check and parse the ``responses`` list.

    Args:
        items: The raw value.
        header: The parsed header.
        problems: List to append problems to.

    Returns:
        Valid responses.
    """
    if not isinstance(items, list) or not items:
        problems.append("'responses' must be a non-empty list")
        return []
    responses: list[Response] = []
    seen: set[tuple[str, str]] = set()
    for index, item in enumerate(items):
        where = f"responses[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue
        rater, passage_id = item.get("rater_id"), item.get("passage_id")
        if not isinstance(rater, str) or not isinstance(passage_id, str):
            problems.append(f"{where} must name a listed rater and a listed passage")
            continue
        if rater not in header.raters or passage_id not in header.passages:
            problems.append(f"{where} must name a listed rater and a listed passage")
            continue
        if (rater, passage_id) in seen:
            problems.append(f"{where} repeats rater {rater!r} on passage {passage_id!r}")
            continue
        seen.add((rater, passage_id))
        marks = _parse_marks_list(
            item.get("marks"), header.passages[passage_id].text, where, problems
        )
        if marks is not None:
            responses.append(Response(rater, passage_id, marks))
    return responses


def _parse_marks_list(
    items: Any, text: str, where: str, problems: list[str]
) -> tuple[Mark, ...] | None:
    """Check one response's marks against the passage text.

    Args:
        items: The raw ``marks`` value.
        text: The passage text.
        where: Location for messages.
        problems: List to append problems to.

    Returns:
        Sorted marks, or None if any mark is invalid.
    """
    if not isinstance(items, list):
        problems.append(f"{where}.marks must be a list (empty if nothing was marked)")
        return None
    marks: list[Mark] = []
    valid = True
    for index, item in enumerate(items):
        spot = f"{where}.marks[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{spot} must be an object")
            valid = False
            continue

        # Offsets must be integers inside the text, and the quoted text must match.
        start, end, quoted = item.get("start"), item.get("end"), item.get("text")
        if not (
            isinstance(start, int)
            and isinstance(end, int)
            and not isinstance(start, bool)
            and not isinstance(end, bool)
            and 0 <= start < end <= len(text)
        ):
            problems.append(f"{spot} needs integer offsets with 0 <= start < end <= {len(text)}")
            valid = False
            continue
        if quoted != text[start:end]:
            problems.append(f"{spot}.text {quoted!r} does not match the passage at {start}-{end}")
            valid = False
            continue
        marks.append(Mark(start, end, quoted))

    # Marks within one response must not overlap.
    marks.sort(key=lambda m: m.start)
    for first, second in pairwise(marks):
        if second.start < first.end:
            problems.append(f"{where} has overlapping marks at {first.start} and {second.start}")
            valid = False
    return tuple(marks) if valid else None


def analyse_passages(
    study: MarksStudy, *, nlp: Language | None = None, familiarity: Familiarity | None = None
) -> dict[str, PassageTerms]:
    """Run the burden pipeline on every passage, keeping exact offsets.

    Args:
        study: The study.
        nlp: spaCy pipeline (default: the configured one).
        familiarity: Word-frequency source (default: wordfreq).

    Returns:
        Each passage's candidate terms with their burden weights.
    """
    pipeline = nlp or load_pipeline()
    lookup = familiarity or WordfreqFamiliarity()
    result: dict[str, PassageTerms] = {}
    for passage_id, passage in study.header.passages.items():
        # The passage text is used verbatim, so term offsets match mark offsets.
        analysis = analyse_document(
            single_paragraph_document(passage.text, paragraph_id=passage_id),
            nlp=pipeline,
            familiarity=lookup,
        )
        paragraph = analysis.paragraphs[0]
        burden = compute_burden(
            [LocatedTerm(passage_id, t) for t in paragraph.terms],
            words=paragraph.words,
            citations=len(paragraph.citations),
            defined=analysis.defined,
        )

        # Every candidate term, weighted 0 unless it is undefined and unfamiliar.
        weights = {t.key: t.weight for t in burden.undefined_terms}
        spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for occurrence in paragraph.terms:
            spans[occurrence.key].append((occurrence.start, occurrence.end))
        result[passage_id] = PassageTerms(
            passage_id=passage_id,
            words=paragraph.words,
            burden_per_1000=burden.burden_per_1000,
            terms=tuple(
                PassageTerm(key, weights.get(key, 0.0), tuple(found))
                for key, found in spans.items()
            ),
        )
    return result


def evaluate_marks_against(
    study: MarksStudy, passages: Mapping[str, PassageTerms]
) -> dict[str, Any]:
    """Compare readers' marks with the burden pipeline's terms and scores.

    Args:
        study: The study.
        passages: The pipeline's view of each passage (from :func:`analyse_passages`).

    Returns:
        Term-level, list-quality and passage-level agreement (see the module
        docstring). Values are None when they cannot be computed.
    """
    by_passage: dict[str, list[Response]] = defaultdict(list)
    for response in study.responses:
        by_passage[response.passage_id].append(response)

    # Term level: each candidate term's mark rate against its weight.
    weights: list[float] = []
    rates: list[float] = []
    for passage_id, responses in by_passage.items():
        for term in passages[passage_id].terms:
            marked = sum(1 for r in responses if _term_marked(term, r))
            weights.append(term.weight)
            rates.append(marked / len(responses))
    flagged = [rate for weight, rate in zip(weights, rates, strict=True) if weight > 0]

    # Recall: how many of the readers' marks the pipeline's terms cover.
    all_marks = [(r.passage_id, m) for r in study.responses for m in r.marks]
    flagged_hits = sum(1 for pid, m in all_marks if _covered(m, passages[pid], flagged_only=True))
    candidate_hits = sum(
        1 for pid, m in all_marks if _covered(m, passages[pid], flagged_only=False)
    )

    # Passage level: burden against marks per 1,000 words.
    burdens: list[float] = []
    mark_density: list[float] = []
    for passage_id, responses in by_passage.items():
        view = passages[passage_id]
        if view.words:
            burdens.append(view.burden_per_1000)
            mean_marks = sum(len(r.marks) for r in responses) / len(responses)
            mark_density.append(mean_marks * 1000 / view.words)

    return {
        "study_id": study.header.study_id,
        "synthetic": study.header.synthetic,
        "responses": len(study.responses),
        "marks": len(all_marks),
        "term_level": {
            "candidate_terms": len(weights),
            "spearman_weight_vs_mark_rate": spearman(weights, rates),
            "auc_weight_for_majority_marked": auc(
                [w for w, r in zip(weights, rates, strict=True) if r >= MAJORITY],
                [w for w, r in zip(weights, rates, strict=True) if r < MAJORITY],
            ),
        },
        "list_quality": {
            "flagged_terms": len(flagged),
            "precision_marked_by_any": _share(sum(1 for r in flagged if r > 0), len(flagged)),
            "precision_marked_by_most": _share(
                sum(1 for r in flagged if r >= MAJORITY), len(flagged)
            ),
            "recall_of_marks_by_flagged_terms": _share(flagged_hits, len(all_marks)),
            "recall_of_marks_by_any_candidate": _share(candidate_hits, len(all_marks)),
        },
        "passage_level": {
            "passages": len(burdens),
            "spearman_burden_vs_marks_per_1000": spearman(burdens, mark_density),
        },
    }


def evaluate_marks(study: MarksStudy) -> dict[str, Any]:
    """Analyse every passage with the burden pipeline and evaluate it.

    Args:
        study: The study.

    Returns:
        The output of :func:`evaluate_marks_against`.
    """
    return evaluate_marks_against(study, analyse_passages(study))


def _term_marked(term: PassageTerm, response: Response) -> bool:
    """Check whether a response marked any occurrence of a term.

    Args:
        term: A candidate term.
        response: One rater's marks on the term's passage.

    Returns:
        True if any mark overlaps any occurrence.
    """
    return any(overlaps_any(m.start, m.end, term.spans) for m in response.marks)


def _covered(mark: Mark, view: PassageTerms, *, flagged_only: bool) -> bool:
    """Check whether a mark overlaps a candidate term.

    Args:
        mark: A reader's mark.
        view: The pipeline's view of the passage.
        flagged_only: Only count terms with a weight above 0.

    Returns:
        True if the mark overlaps a (flagged) term occurrence.
    """
    return any(
        overlaps_any(mark.start, mark.end, term.spans)
        for term in view.terms
        if term.weight > 0 or not flagged_only
    )


def _share(part: int, whole: int) -> float | None:
    """Return a ratio, or None for an empty denominator.

    Args:
        part: Numerator.
        whole: Denominator.

    Returns:
        ``part / whole`` or None.
    """
    return part / whole if whole else None
