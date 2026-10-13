"""Tests of the rubric loader and the committed rubric_v1 files."""

from __future__ import annotations

import pytest

from rbbench.paths import RUBRIC_DIR
from rbbench.rubric import Rubric, RubricError, Unit, parse_rubric


def test_rubric_v1_has_the_required_separate_codes(
    rubric: Rubric, clean_claim_labels: dict[str, str]
) -> None:
    """rubric_v1 carries every code Plan.md Phase 1 asks for, each separately."""
    assert rubric.id == "rubric_v1"
    assert rubric.status == "DRAFT"
    claim_codes = {code.id for code in rubric.codes_for(Unit.CLAIM)}
    assert claim_codes == set(clean_claim_labels)
    assert [c.id for c in rubric.codes_for(Unit.PARAGRAPH)] == ["dropped_limitation"]
    assert rubric.code("support").value_ids == ("supported", "unsupported", "contradicted")
    assert rubric.code("added_information").value_ids == ("no", "factual", "non_factual")
    assert rubric.code("lost_hedge").value_ids == ("no", "yes")
    overgen = [c.id for c in rubric.codes if c.group == "overgeneralisation"]
    assert overgen == ["overgen_generic", "overgen_present_tense", "overgen_action_guiding"]


def test_human_readable_rubric_and_guide_cover_every_code(rubric: Rubric) -> None:
    """rubric_v1.md and the rater guide mention every code and are marked DRAFT."""
    for name in ("rubric_v1.md", "rater_guide_v1.md"):
        text = (RUBRIC_DIR / name).read_text(encoding="utf-8")
        assert "DRAFT" in text, name
        for code_id in [c.id for c in rubric.codes] + [d.id for d in rubric.derived]:
            assert f"`{code_id}`" in text, f"{name} lacks {code_id}"


def test_validate_labels_reports_missing_unknown_and_bad_values(
    rubric: Rubric, clean_claim_labels: dict[str, str]
) -> None:
    """Validation names each missing code, unknown code and disallowed value."""
    assert rubric.validate_labels(Unit.CLAIM, clean_claim_labels) == []
    labels = {**clean_claim_labels, "support": "maybe", "extra": "no"}
    del labels["spin"]
    errors = rubric.validate_labels(Unit.CLAIM, labels)
    assert "missing code 'spin'" in errors
    assert "unknown code 'extra' for unit 'claim'" in errors
    assert any("'support': value 'maybe'" in e for e in errors)


def test_derive_overgeneralisation_is_any_of_three_shifts(
    rubric: Rubric, clean_claim_labels: dict[str, str]
) -> None:
    """The derived code is yes when any shift is yes, and only claims get it."""
    assert rubric.derive(Unit.CLAIM, clean_claim_labels) == {"overgeneralisation": "no"}
    shifted = {**clean_claim_labels, "overgen_present_tense": "yes"}
    assert rubric.derive(Unit.CLAIM, shifted) == {"overgeneralisation": "yes"}
    assert rubric.derive(Unit.PARAGRAPH, {"dropped_limitation": "yes"}) == {}


def test_yaml_no_value_is_not_parsed_as_boolean(rubric: Rubric) -> None:
    """The quoted "no" value stays a string (YAML 1.1 would read bare no as False)."""
    assert "no" in rubric.code("added_information").value_ids


@pytest.mark.parametrize(
    ("snippet", "message"),
    [
        ("codes: [{id: a, unit: claim, kind: binary, question: q, values: []}]", "must not list"),
        ("codes: [{id: a, unit: claim, kind: nominal, question: q, values: []}]", "two unique"),
        ("codes: [{id: a, unit: sentence, kind: binary, question: q}]", "unit must be"),
        ("codes: [{id: a, unit: claim, kind: scale, question: q}]", "kind must be"),
        (
            "codes: [{id: a, unit: claim, kind: binary, question: q},"
            " {id: a, unit: claim, kind: binary, question: q}]",
            "duplicate",
        ),
        (
            "codes: [{id: a, unit: claim, kind: binary, question: q}]\n"
            "derived: [{id: d, unit: paragraph, rule: any_yes, of: [a]}]",
            "not a binary paragraph code",
        ),
    ],
)
def test_invalid_rubrics_are_rejected(snippet: str, message: str) -> None:
    """Each structural rule produces a RubricError naming the problem."""
    text = f"id: r\nstatus: DRAFT\nunits: {{claim: c, paragraph: p}}\n{snippet}\n"
    with pytest.raises(RubricError, match=message):
        parse_rubric(text)
