"""Study-type classification from PubMed publication types and JATS article type.

Four study types (decisions.md §1.4): randomised trial, observational study,
lab/mechanistic work, review. The classification is deliberately strict:
an article whose metadata points to more than one type, or whose JATS
article type disagrees with its PubMed type, is left unclassified and not
proposed, because a mislabelled slot would undermine the spread the
benchmark is meant to have.

Lab/mechanistic work has no PubMed publication type. It is recognised by the
search that found the article (a MeSH filter for animal or cell studies
without human subjects, recorded in the selection config), plus a JATS
research article with no clinical or review publication type.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class StudyType(StrEnum):
    """The benchmark's study-type strata."""

    RANDOMISED_TRIAL = "randomised_trial"
    OBSERVATIONAL = "observational"
    LAB_MECHANISTIC = "lab_mechanistic"
    REVIEW = "review"


# PubMed publication types that identify each clinical or review design.
_TYPE_PUBTYPES: dict[StudyType, frozenset[str]] = {
    StudyType.RANDOMISED_TRIAL: frozenset({"Randomized Controlled Trial"}),
    StudyType.OBSERVATIONAL: frozenset({"Observational Study"}),
    StudyType.REVIEW: frozenset({"Review", "Systematic Review", "Meta-Analysis"}),
}

# Clinical designs that rule out "lab/mechanistic" even without a match above.
_CLINICAL_PUBTYPES = frozenset(
    {
        "Clinical Trial",
        "Clinical Trial, Phase I",
        "Clinical Trial, Phase II",
        "Clinical Trial, Phase III",
        "Clinical Trial, Phase IV",
        "Controlled Clinical Trial",
        "Pragmatic Clinical Trial",
        "Case Reports",
        "Clinical Study",
        "Multicenter Study",
    }
)

# JATS @article-type values acceptable for each type. Systematic reviews and
# meta-analyses are often typed research-article by publishers.
_JATS_TYPES: dict[StudyType, frozenset[str]] = {
    StudyType.RANDOMISED_TRIAL: frozenset({"research-article"}),
    StudyType.OBSERVATIONAL: frozenset({"research-article"}),
    StudyType.LAB_MECHANISTIC: frozenset({"research-article"}),
    StudyType.REVIEW: frozenset({"review-article", "research-article"}),
}


@dataclass(frozen=True, slots=True)
class Classification:
    """The outcome of classifying one article.

    Attributes:
        study_type: The type, or None when the evidence is missing or mixed.
        basis: Human-readable evidence for the type (or for the refusal).
    """

    study_type: StudyType | None
    basis: str


def classify(
    pubtypes: Sequence[str], jats_article_type: str | None, *, lab_query_match: bool
) -> Classification:
    """Classify an article into one study type, or refuse.

    Args:
        pubtypes: PubMed publication types from esummary.
        jats_article_type: ``article/@article-type`` from the JATS, or None if
            the JATS has not been read yet (classification is then provisional
            on publication types only).
        lab_query_match: Whether the article came from the lab/mechanistic
            search (animal or cell studies without human subjects).

    Returns:
        The classification with its basis.
    """
    types = set(pubtypes)
    matched = [kind for kind, names in _TYPE_PUBTYPES.items() if types & names]
    pubtype_text = ", ".join(sorted(types)) or "none"

    # Mixed signals (e.g. a trial also typed as a review) are never guessed.
    if len(matched) > 1:
        names = " and ".join(sorted(k.value for k in matched))
        return Classification(None, f"ambiguous PubMed publication types ({names})")
    if matched:
        study_type = matched[0]
    elif lab_query_match and not types & _CLINICAL_PUBTYPES:
        study_type = StudyType.LAB_MECHANISTIC
    else:
        return Classification(None, f"no study type from publication types ({pubtype_text})")

    # The publisher's own article type must agree, once the JATS is available.
    basis = f"PubMed publication types: {pubtype_text}"
    if study_type is StudyType.LAB_MECHANISTIC:
        basis += "; matched the lab/mechanistic MeSH search"
    if jats_article_type is not None:
        if jats_article_type not in _JATS_TYPES[study_type]:
            return Classification(
                None,
                f"JATS article-type {jats_article_type!r} disagrees with {study_type.value}",
            )
        basis += f"; JATS article-type: {jats_article_type}"
    return Classification(study_type, basis)


# Phrases an abstract uses to name its own design. PubMed publication types
# alone mislabel secondary analyses and modelling papers (seen in the first
# selection run: a cytokine sub-study typed as a trial, a dosing model typed as
# a meta-analysis), so the paper's own abstract must confirm the design.
_DESIGN_PATTERNS: dict[StudyType, re.Pattern[str]] = {
    StudyType.RANDOMISED_TRIAL: re.compile(
        r"\b(randomi[sz]ed (controlled |clinical )?trial|randomly (assigned|allocated))\b",
        re.IGNORECASE,
    ),
    StudyType.OBSERVATIONAL: re.compile(
        r"\b(cohort|cross-sectional|case-control|observational|prospective(ly)? (study|enrolled)"
        r"|retrospective (study|analysis|review)|surveillance)\b",
        re.IGNORECASE,
    ),
    StudyType.REVIEW: re.compile(
        r"\b(systematic(ally)? review(ed)?|meta-analys[ie]s|scoping review|literature review)\b",
        re.IGNORECASE,
    ),
    StudyType.LAB_MECHANISTIC: re.compile(
        r"\b(mice|mouse|rats?|zebrafish|drosophila|flies|worms?|c\. elegans|yeast|in vitro"
        r"|cells?|cultured|organoids?|bacteria[l]?)\b",
        re.IGNORECASE,
    ),
}


# A trial slot wants a primary trial report, not a secondary or post hoc analysis.
_EXCLUDE_PATTERNS: dict[StudyType, re.Pattern[str]] = {
    StudyType.RANDOMISED_TRIAL: re.compile(
        r"\b(secondary analys[ie]s|post[- ]hoc|ancillary (study|analysis)|sub-?study)\b",
        re.IGNORECASE,
    ),
}


def design_evidence(study_type: StudyType, abstract: str) -> str | None:
    """Find the phrase in an abstract that names the study's design.

    Args:
        study_type: The type assigned from metadata.
        abstract: The main abstract's text.

    Returns:
        The first matching phrase, or None when the abstract does not confirm
        the design or (for trials) describes a secondary analysis.
    """
    exclude = _EXCLUDE_PATTERNS.get(study_type)
    if exclude is not None and exclude.search(abstract):
        return None
    match = _DESIGN_PATTERNS[study_type].search(abstract)
    return match.group(0) if match else None
