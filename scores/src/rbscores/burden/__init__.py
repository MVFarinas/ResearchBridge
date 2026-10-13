"""PROVISIONAL prior-knowledge burden score: what the text assumes (decisions.md §2.4).

Pipeline: :mod:`~rbscores.burden.terms` (candidate terms) ->
:mod:`~rbscores.burden.definitions` (terms the text defines, including
Schwartz-Hearst abbreviations from :mod:`~rbscores.burden.abbreviations`) ->
:mod:`~rbscores.burden.references` (citation markers: external results leaned on) ->
:mod:`~rbscores.burden.score` (weighting and the per-1,000-word score).
"""

from rbscores.burden.definitions import Definition, DefinitionKind, find_definitions
from rbscores.burden.score import (
    BurdenParams,
    BurdenResult,
    DefinedTerms,
    TermBurden,
    TermLocation,
    compute_burden,
)
from rbscores.burden.terms import TermOccurrence, extract_terms

__all__ = [
    "BurdenParams",
    "BurdenResult",
    "DefinedTerms",
    "Definition",
    "DefinitionKind",
    "TermBurden",
    "TermLocation",
    "TermOccurrence",
    "compute_burden",
    "extract_terms",
    "find_definitions",
]
