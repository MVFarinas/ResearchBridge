"""The PROVISIONAL composite readability score.

Method: each of the five features (:data:`FEATURE_NAMES`) is z-scored against
fixed reference statistics, and the composite is the unweighted mean of the
five z-scores. Higher means harder; 0 means "like a typical stretch of
research-article body text" in the reference sample.

Equal weights are a deliberate placeholder: there is no human data yet to fit
weights to, and fitting them to validation 1's lay-versus-technical pairs
would make validation 1 circular. Weights should be revisited once validation
2's pairwise human judgements exist.

The reference statistics are not computed from the text being scored, so a
score does not depend on what else is in the batch. The packaged reference
(``reference_v0.json``) is produced by ``rbscores validation1 calibrate`` from
body-text windows of training-split articles of the PLOS and eLife corpora,
disjoint from the validation-split papers used in validation 1. See
scores/reports/validation_1.md.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from rbscores.readability.features import FEATURE_NAMES, ReadabilityFeatures

DEFAULT_REFERENCE_FILE = "reference_v0.json"


class ReferenceStatsError(ValueError):
    """Raised when reference statistics are missing or malformed."""


@dataclass(frozen=True, slots=True)
class FeatureReference:
    """Mean and standard deviation of one feature in the reference sample.

    Attributes:
        mean: Reference mean.
        sd: Reference standard deviation (positive).
    """

    mean: float
    sd: float


@dataclass(frozen=True, slots=True)
class ReferenceStats:
    """Fixed statistics the composite z-scores against.

    Attributes:
        version: Identifier recorded in every score report.
        description: How and from what the statistics were computed.
        units: Number of text units in the reference sample.
        features: Per-feature mean and SD, keyed by feature name.
    """

    version: str
    description: str
    units: int
    features: Mapping[str, FeatureReference]

    def to_json(self) -> dict[str, Any]:
        """Return the statistics in the JSON file format.

        Returns:
            A JSON-serialisable mapping, readable by :func:`reference_from_json`.
        """
        return {
            "version": self.version,
            "description": self.description,
            "units": self.units,
            "features": {
                name: {"mean": ref.mean, "sd": ref.sd} for name, ref in self.features.items()
            },
        }


def reference_from_json(data: Mapping[str, Any]) -> ReferenceStats:
    """Build reference statistics from their JSON form, checking them.

    Args:
        data: Parsed JSON with ``version``, ``description``, ``units`` and
            ``features`` (each with ``mean`` and ``sd``).

    Returns:
        The statistics.

    Raises:
        ReferenceStatsError: If a field or feature is missing, or an SD is not positive.
    """
    # Parse every field, turning any missing or mistyped one into one error.
    try:
        raw_features = data["features"]
        features = {
            name: FeatureReference(
                mean=float(raw_features[name]["mean"]), sd=float(raw_features[name]["sd"])
            )
            for name in FEATURE_NAMES
        }
        stats = ReferenceStats(
            version=str(data["version"]),
            description=str(data["description"]),
            units=int(data["units"]),
            features=features,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ReferenceStatsError(f"malformed reference statistics: {exc!r}") from exc

    # A zero or negative SD would make z-scores meaningless (or divide by zero).
    bad = [name for name, ref in features.items() if not ref.sd > 0]
    if bad:
        raise ReferenceStatsError(f"reference SD must be positive for: {', '.join(bad)}")
    return stats


def load_reference(path: str | Path | None = None) -> ReferenceStats:
    """Load reference statistics from a file, or the packaged default.

    Args:
        path: A JSON file, or None for the packaged ``reference_v0.json``.

    Returns:
        The statistics.

    Raises:
        ReferenceStatsError: If the file is malformed.
        OSError: If the file cannot be read.
    """
    if path is None:
        text = (
            resources.files("rbscores.readability")
            .joinpath(DEFAULT_REFERENCE_FILE)
            .read_text(encoding="utf-8")
        )
    else:
        text = Path(path).read_text(encoding="utf-8")
    return reference_from_json(json.loads(text))


def z_scores(features: ReadabilityFeatures, reference: ReferenceStats) -> dict[str, float]:
    """Z-score each feature against the reference.

    Args:
        features: Features of one unit.
        reference: Reference statistics.

    Returns:
        Feature name to z-score (positive = harder than the reference mean).
    """
    values = features.values()
    return {
        name: (values[name] - reference.features[name].mean) / reference.features[name].sd
        for name in FEATURE_NAMES
    }


def composite_score(features: ReadabilityFeatures, reference: ReferenceStats) -> float:
    """Return the PROVISIONAL composite: the mean of the five z-scores.

    Args:
        features: Features of one unit.
        reference: Reference statistics.

    Returns:
        The composite; higher is harder, 0 is the reference mean.
    """
    scores = z_scores(features, reference)
    return sum(scores.values()) / len(scores)
