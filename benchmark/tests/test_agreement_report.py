"""Tests of the per-code agreement report and adjudication merge (SYNTHETIC ratings)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from rbbench.agreement import (
    Basis,
    Policy,
    RatingsError,
    agreement_report,
    final_labels_by_unit,
    merge_labels,
    read_adjudications,
    write_disagreements,
)
from rbbench.agreement.adjudicate import AdjudicationError
from rbbench.ratings import Rating, load_ratings, save_ratings
from rbbench.rubric import Rubric, Unit

Factory = Callable[..., Rating]


def _two_synthetic_raters(make: Factory) -> list[Rating]:
    """Four claims; the raters disagree on lost_hedge for c3 only."""
    ratings = []
    for rater in ("synthetic-r1", "synthetic-r2"):
        ratings.append(make(rater, "c1"))
        ratings.append(make(rater, "c2", support="unsupported", added_information="factual"))
        ratings.append(make(rater, "c3", lost_hedge="yes" if rater == "synthetic-r1" else "no"))
        ratings.append(make(rater, "c4", lost_hedge="yes", overgen_generic="yes"))
    return ratings


def test_report_computes_kappa_alpha_and_prevalence(
    rubric: Rubric, make_synthetic_rating: Factory
) -> None:
    """lost_hedge: 3 of 4 units agree; kappa and alpha match hand calculation."""
    report = {
        entry.code_id: entry
        for entry in agreement_report(_two_synthetic_raters(make_synthetic_rating), rubric)
    }
    hedge = report["lost_hedge"]
    assert hedge.raters == ("synthetic-r1", "synthetic-r2")
    assert hedge.n_units == 4
    assert hedge.observed_agreement == pytest.approx(0.75)
    # r1: yes on c3, c4; r2: yes on c4. p_o = .75, p_e = .5*.25 + .5*.75 = .5.
    assert hedge.cohen_kappa == pytest.approx(0.5)
    assert hedge.fleiss_units == 4
    assert hedge.krippendorff_alpha is not None
    assert hedge.value_counts == {"no": 5, "yes": 3}
    # A code with no variation at all has undefined kappa and alpha, with a note.
    spin = report["spin"]
    assert spin.cohen_kappa is None
    assert spin.krippendorff_alpha is None
    assert any("undefined" in note for note in spin.notes)
    # The derived code is reported and follows overgen_generic here.
    assert report["overgeneralisation"].derived
    assert report["overgeneralisation"].value_counts == {"no": 6, "yes": 2}
    # Paragraph-level code with no paragraph ratings: zero units.
    assert report["dropped_limitation"].n_units == 0


def test_duplicate_rating_by_one_rater_is_an_error(
    rubric: Rubric, make_synthetic_rating: Factory
) -> None:
    """One rater rating the same unit twice is refused, not silently merged."""
    ratings = [make_synthetic_rating("r1", "c1"), make_synthetic_rating("r1", "c1")]
    with pytest.raises(RatingsError):
        agreement_report(ratings, rubric)


def test_merge_resolves_agreement_and_leaves_disagreement_unresolved(
    rubric: Rubric, make_synthetic_rating: Factory
) -> None:
    """Unanimous codes get a value; the disagreeing code stays unresolved."""
    finals = merge_labels(_two_synthetic_raters(make_synthetic_rating), rubric)
    by_key = {(f.unit_id, f.code_id): f for f in finals}
    assert by_key[("c2", "support")].value == "unsupported"
    assert by_key[("c2", "support")].basis is Basis.UNANIMOUS
    assert by_key[("c3", "lost_hedge")].value is None
    assert by_key[("c3", "lost_hedge")].basis is Basis.UNRESOLVED
    assert by_key[("c3", "lost_hedge")].rater_values == {
        "synthetic-r1": "yes",
        "synthetic-r2": "no",
    }
    assert sum(f.basis is Basis.UNRESOLVED for f in finals) == 1


def test_disagreement_csv_round_trip_applies_adjudication(
    tmp_path: Path, rubric: Rubric, make_synthetic_rating: Factory
) -> None:
    """Exported disagreements, once filled in, resolve the merge."""
    ratings = _two_synthetic_raters(make_synthetic_rating)
    path = tmp_path / "disagreements.csv"
    assert write_disagreements(path, merge_labels(ratings, rubric), rubric) == 1
    # Simulate the adjudicator filling in the blank columns.
    text = path.read_text(encoding="utf-8").replace("no|yes,,,", "no|yes,yes,synthetic-adj,")
    path.write_text(text, encoding="utf-8")
    adjudications = read_adjudications(path)
    assert adjudications == {("claim", "c3", "lost_hedge"): "yes"}
    finals = merge_labels(ratings, rubric, adjudications=adjudications)
    resolved = {(f.unit_id, f.code_id): f for f in finals}[("c3", "lost_hedge")]
    assert (resolved.value, resolved.basis) == ("yes", Basis.ADJUDICATED)
    grouped = final_labels_by_unit(finals, rubric)
    assert grouped[(Unit.CLAIM, "c4")]["overgeneralisation"] == "yes"
    assert grouped[(Unit.CLAIM, "c1")]["overgeneralisation"] == "no"


def test_adjudication_rejects_bad_values_and_anonymous_rows(
    tmp_path: Path, rubric: Rubric, make_synthetic_rating: Factory
) -> None:
    """A value the code does not allow, or a row without adjudicator, is an error."""
    ratings = _two_synthetic_raters(make_synthetic_rating)
    with pytest.raises(AdjudicationError):
        merge_labels(ratings, rubric, adjudications={("claim", "c3", "lost_hedge"): "maybe"})
    path = tmp_path / "anon.csv"
    path.write_text(
        "unit,unit_id,code_id,adjudicated_value,adjudicator\nclaim,c3,lost_hedge,yes,\n",
        encoding="utf-8",
    )
    with pytest.raises(AdjudicationError, match="without adjudicator"):
        read_adjudications(path)


def test_majority_policy_needs_a_strict_majority(
    rubric: Rubric, make_synthetic_rating: Factory
) -> None:
    """Two of three raters decide under 'majority'; unanimous policy does not."""
    ratings = [
        make_synthetic_rating("r1", "c1", spin="yes"),
        make_synthetic_rating("r2", "c1", spin="yes"),
        make_synthetic_rating("r3", "c1", spin="no"),
    ]
    majority = {f.code_id: f for f in merge_labels(ratings, rubric, policy=Policy.MAJORITY)}
    assert (majority["spin"].value, majority["spin"].basis) == ("yes", Basis.MAJORITY)
    strict = {f.code_id: f for f in merge_labels(ratings, rubric)}
    assert strict["spin"].basis is Basis.UNRESOLVED


def test_ratings_round_trip_through_jsonl(tmp_path: Path, make_synthetic_rating: Factory) -> None:
    """Saved ratings load back identical, keeping the synthetic flag."""
    ratings = [make_synthetic_rating("r1", "c1", spin="yes")]
    path = tmp_path / "ratings.jsonl"
    assert save_ratings(path, ratings) == 1
    loaded = load_ratings(path)
    assert loaded == ratings
    assert loaded[0].synthetic
