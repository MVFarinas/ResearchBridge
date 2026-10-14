"""Tests for the readability features, the composite and the Flesch-Kincaid baseline."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest
from spacy.language import Language

from rbscores.familiarity import Familiarity, WordfreqFamiliarity
from rbscores.readability.baseline import count_syllables, flesch_kincaid_grade
from rbscores.readability.composite import (
    ReferenceStats,
    ReferenceStatsError,
    composite_score,
    load_reference,
    reference_from_json,
    z_scores,
)
from rbscores.readability.features import (
    FEATURE_NAMES,
    ReadabilityFeatures,
    SentenceStats,
    aggregate,
    is_word,
    parse_depth,
    sentence_stats,
)
from rbscores.readability.nominalisations import is_nominalisation

SyntheticFactory = Callable[..., Familiarity]


def test_parse_depth_counts_nesting(nlp: Language) -> None:
    """Depth counts tokens from the root: "The" -> "dog" -> "barked" is 3; nesting adds more."""
    assert parse_depth(next(nlp("Stop.").sents)) == 1
    simple = parse_depth(next(nlp("The dog barked.").sents))
    nested = parse_depth(
        next(nlp("The dog that the cat that the boy owned chased barked loudly.").sents)
    )
    assert simple == 3
    assert nested > simple + 1


def test_passive_sentences_are_detected(
    nlp: Language, wordfreq_familiarity: WordfreqFamiliarity
) -> None:
    """Passive clauses are flagged; active ones are not."""
    doc = nlp("The samples were analysed by the team. The team analysed the samples.")
    passive, active = sentence_stats(doc, wordfreq_familiarity)
    assert passive.passive is True
    assert active.passive is False


def test_words_exclude_punctuation_but_include_numbers(nlp: Language) -> None:
    """Numbers are words; punctuation is not."""
    doc = nlp("We tested 12 mice, twice.")
    assert [t.text for t in doc if is_word(t)] == ["We", "tested", "12", "mice", "twice"]


@pytest.mark.parametrize(
    ("sentence", "expected"),
    [
        ("The utilisation of resources improved.", ["utilisation"]),
        ("The investigation and the measurement were long.", ["investigation", "measurement"]),
        ("Science in the city is a community effort.", []),
        ("They investigated it.", []),
    ],
)
def test_nominalisations(nlp: Language, sentence: str, expected: list[str]) -> None:
    """Suffix nouns count; stop-listed, short and non-noun words do not."""
    doc = nlp(sentence)
    assert [t.text for t in doc if is_nominalisation(t)] == expected


def test_jargon_bands_use_word_forms(nlp: Language, make_familiarity: SyntheticFactory) -> None:
    """Rare words count 1, mid-frequency words count 0.5 (synthetic frequencies)."""
    familiarity = make_familiarity({"nephrons": 1.0, "filter": 3.5})
    (stats,) = sentence_stats(nlp("Nephrons filter blood."), familiarity)
    assert (stats.alphabetic_words, stats.rare_words, stats.mid_words) == (3, 1, 1)
    features = aggregate([stats])
    assert features is not None
    assert features.jargon_density == pytest.approx((1 + 0.5) / 3)


def test_aggregate_pools_sentences() -> None:
    """Features pool sentence counts rather than averaging paragraph scores."""
    stats = [
        SentenceStats(
            words=10,
            depth=4,
            passive=True,
            nominalisations=1,
            alphabetic_words=10,
            rare_words=2,
            mid_words=0,
        ),
        SentenceStats(
            words=30,
            depth=8,
            passive=False,
            nominalisations=2,
            alphabetic_words=20,
            rare_words=0,
            mid_words=2,
        ),
    ]
    features = aggregate(stats)
    assert features == ReadabilityFeatures(
        sentences=2,
        words=40,
        mean_sentence_length=20.0,
        mean_parse_depth=6.0,
        nominalisation_rate=100 * 3 / 40,
        passive_rate=0.5,
        jargon_density=(2 + 0.5 * 2) / 30,
    )
    assert list(features.values()) == list(FEATURE_NAMES)


def test_aggregate_of_nothing_is_none() -> None:
    """A unit without words has no features."""
    assert aggregate([]) is None


def _features(**overrides: float) -> ReadabilityFeatures:
    """Build features with every value 1.0 unless overridden."""
    values = dict.fromkeys(FEATURE_NAMES, 1.0) | overrides
    return ReadabilityFeatures(sentences=1, words=10, **values)


def test_composite_is_mean_of_z_scores(synthetic_reference: ReferenceStats) -> None:
    """With mean 0 and SD 1, z-scores are the raw values and the composite their mean."""
    features = _features(mean_sentence_length=6.0)
    assert z_scores(features, synthetic_reference)["mean_sentence_length"] == 6.0
    assert composite_score(features, synthetic_reference) == pytest.approx((6 + 1 + 1 + 1 + 1) / 5)


def test_composite_uses_reference_mean_and_sd() -> None:
    """Z-scores subtract the reference mean and divide by its SD."""
    reference = reference_from_json(
        {
            "version": "synthetic",
            "description": "SYNTHETIC",
            "units": 3,
            "features": {name: {"mean": 1.0, "sd": 2.0} for name in FEATURE_NAMES},
        }
    )
    features = _features(jargon_density=5.0)
    assert z_scores(features, reference)["jargon_density"] == 2.0
    assert composite_score(features, reference) == pytest.approx(2.0 / 5)


def test_reference_rejects_missing_features_and_zero_sd() -> None:
    """Malformed reference statistics fail loudly."""
    good = {name: {"mean": 0.0, "sd": 1.0} for name in FEATURE_NAMES}
    with pytest.raises(ReferenceStatsError, match="malformed"):
        reference_from_json({"version": "v", "description": "d", "units": 1, "features": {}})
    bad = good | {"passive_rate": {"mean": 0.0, "sd": 0.0}}
    with pytest.raises(ReferenceStatsError, match="passive_rate"):
        reference_from_json({"version": "v", "description": "d", "units": 1, "features": bad})


def test_packaged_reference_loads_and_is_marked_provisional() -> None:
    """The committed reference statistics are complete and say they are provisional."""
    reference = load_reference()
    assert "provisional" in reference.version
    assert reference.description.startswith("PROVISIONAL")
    assert reference.units > 100
    assert set(reference.features) == set(FEATURE_NAMES)
    assert reference.to_json()["features"]["jargon_density"]["sd"] > 0


def test_reference_loads_from_a_file(tmp_path: Path) -> None:
    """A reference written with to_json() reads back identically from a path."""
    synthetic = reference_from_json(
        {
            "version": "synthetic-file-reference",
            "description": "SYNTHETIC: for this test only",
            "units": 3,
            "features": {name: {"mean": 1.5, "sd": 0.5} for name in FEATURE_NAMES},
        }
    )
    path = tmp_path / "reference.json"
    path.write_text(json.dumps(synthetic.to_json()), encoding="utf-8")
    assert load_reference(path) == synthetic
    assert load_reference(str(path)).version == "synthetic-file-reference"


def test_reference_file_with_invalid_json_fails(tmp_path: Path) -> None:
    """A reference file that is not JSON raises a ValueError, which the CLI reports."""
    path = tmp_path / "reference.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValueError, match="Expecting property name"):
        load_reference(path)


@pytest.mark.parametrize(
    ("word", "syllables"),
    [("cat", 1), ("table", 2), ("make", 1), ("computer", 3), ("rhythm", 1), ("42", 0), ("I", 1)],
)
def test_count_syllables(word: str, syllables: int) -> None:
    """The vowel-group heuristic gives the expected counts."""
    assert count_syllables(word) == syllables


def test_flesch_kincaid_grade_formula() -> None:
    """One sentence of four one-syllable words: 0.39 x 4 + 11.8 x 1 - 15.59."""
    assert flesch_kincaid_grade([["The", "cat", "sat", "down"]]) == pytest.approx(
        0.39 * 4 + 11.8 - 15.59
    )
    assert flesch_kincaid_grade([[], ["!"]]) is None
