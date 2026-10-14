"""PROVISIONAL readability score: how hard the prose itself is (decisions.md §2.4).

See :mod:`rbscores.readability.features` for the five features and
:mod:`rbscores.readability.composite` for how they are combined.
"""

from rbscores.readability.composite import (
    ReferenceStats,
    composite_score,
    load_reference,
    z_scores,
)
from rbscores.readability.features import (
    FEATURE_NAMES,
    ReadabilityFeatures,
    SentenceStats,
    aggregate,
    sentence_stats,
)

__all__ = [
    "FEATURE_NAMES",
    "ReadabilityFeatures",
    "ReferenceStats",
    "SentenceStats",
    "aggregate",
    "composite_score",
    "load_reference",
    "sentence_stats",
    "z_scores",
]
