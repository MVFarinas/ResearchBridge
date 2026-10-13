"""No displayable or rewriteable query can return anything that fails the gate.

Two independent layers are tested:

1. Database check constraints refuse stored permissions that contradict the
   decisions.md §1.1 table, whatever code tries to write them.
2. Every combination of gate status, licence family, current/old version,
   retraction, and figure/paragraph override is created (synthetic rows), and
   the gated querysets are compared with an independent Python statement of
   the rules. The comparison is exact: nothing that fails is returned, and
   nothing that passes is hidden.
"""

from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from django.db import IntegrityError, transaction
from support import synthetic_version

from rb_backend.corpus import access
from rb_backend.corpus.models import (
    Figure,
    GatedPermissions,
    GateStatus,
    Paper,
    PaperVersion,
    Paragraph,
    Section,
    Source,
)
from rbcore.licences import Licence, LicenceFamily, derive_permissions

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 13, tzinfo=UTC)
FAMILIES = [
    LicenceFamily.CC_BY,
    LicenceFamily.CC_BY_SA,
    LicenceFamily.CC_BY_ND,
    LicenceFamily.CC_BY_NC_ND,
    LicenceFamily.TDM,
    LicenceFamily.ARXIV_NONEXCLUSIVE,
    LicenceFamily.UNKNOWN,
]
STATUSES = list(GateStatus)


def decide_row(row: GatedPermissions, status: GateStatus, family: LicenceFamily) -> None:
    """Store a synthetic decision through the model's own setter."""
    licence = Licence(family, "4.0" if Licence(family).is_creative_commons else None)
    row.set_decision(
        status=status,
        licence=licence,
        permissions=derive_permissions(licence),
        source="synthetic",
        reasons=["synthetic test decision"],
        decided_at=NOW,
    )


# --- Independent statement of the rules ----------------------------------------


def own_ok(status: str, family: str) -> bool:
    """A row's own decision allows display."""
    return status == GateStatus.APPROVED and Licence(LicenceFamily(family)).is_open


def own_rewrite_ok(status: str, family: str) -> bool:
    """A row's own decision allows rewriting."""
    return own_ok(status, family) and not Licence(LicenceFamily(family)).no_derivatives


def version_display_ok(v: PaperVersion) -> bool:
    """The version may be displayed."""
    return v.is_current and own_ok(v.gate_status, v.licence_family)


def version_rewrite_ok(v: PaperVersion) -> bool:
    """The version may be rewritten."""
    return (
        version_display_ok(v)
        and own_rewrite_ok(v.gate_status, v.licence_family)
        and not v.paper.is_retracted
    )


# --- Layer 1: database constraints -----------------------------------------------


@pytest.mark.parametrize(
    ("description", "changes"),
    [
        ("display while under review", {"gate_status": GateStatus.REVIEW, "can_display": True}),
        ("display while pending", {"gate_status": GateStatus.PENDING, "can_display": True}),
        ("rewrite without display", {"can_display": False, "can_rewrite": True}),
        ("display under TDM", {"licence_family": "tdm"}),
        ("display under an unknown licence", {"licence_family": "unknown"}),
        ("rewrite under CC BY-ND", {"licence_family": "cc-by-nd"}),
        ("rewrite under CC BY-NC-ND", {"licence_family": "cc-by-nc-nd"}),
        ("rewrite without an output licence", {"output_licence_family": ""}),
        ("output licence without rewrite", {"can_rewrite": False}),
    ],
)
@pytest.mark.parametrize("model", ["version", "paragraph", "figure"])
def test_database_refuses_permissions_that_break_the_table(
    description: str, changes: dict[str, object], model: str
) -> None:
    """Writing contradictory permissions fails at the database, for every gated table."""
    version = synthetic_version()
    section = Section.objects.create(version=version, stable_id="body", kind="body", position=0)
    rows: dict[str, Callable[[], GatedPermissions]] = {
        "version": lambda: version,
        "paragraph": lambda: Paragraph.objects.create(
            version=version,
            section=section,
            stable_id="body-p1",
            kind="p",
            text="t",
            text_sha256="0",
            position=0,
        ),
        "figure": lambda: Figure.objects.create(
            version=version, stable_id="fig1", kind=Figure.Kind.FIGURE, position=0
        ),
    }
    row = rows[model]()
    decide_row(row, GateStatus.APPROVED, LicenceFamily.CC_BY)
    row.save()
    for name, value in changes.items():
        setattr(row, name, value)
    with pytest.raises(IntegrityError), transaction.atomic():
        row.save()


def test_database_refuses_two_current_versions() -> None:
    """A paper has at most one current version, so a stale one cannot be served."""
    first = synthetic_version()
    with pytest.raises(IntegrityError), transaction.atomic():
        synthetic_version(version_number=2, paper=first.paper)


def test_database_refuses_raw_update_that_opens_a_rejected_paper() -> None:
    """Even a bulk UPDATE that bypasses model code cannot open a rejected version."""
    version = synthetic_version()
    decide_row(version, GateStatus.REJECTED, LicenceFamily.TDM)
    version.save()
    with pytest.raises(IntegrityError), transaction.atomic():
        PaperVersion.objects.filter(pk=version.pk).update(can_display=True)


# --- Layer 2: exhaustive queryset matrix -------------------------------------------


@pytest.fixture
def matrix() -> list[PaperVersion]:
    """Synthetic versions covering every state, each with every figure and paragraph state."""
    versions: list[PaperVersion] = []
    combos = itertools.product(STATUSES, FAMILIES, [True, False], [False, True])
    for n, (status, family, current, retracted) in enumerate(combos):
        paper = Paper.objects.create(
            pmcid=f"PMC9{n:08d}",
            is_retracted=retracted,
            retraction_source="synthetic" if retracted else "",
        )
        version = PaperVersion(
            paper=paper,
            source=Source.PMC,
            source_version_id=f"{paper.pmcid}.1",
            version_number=1,
            is_current=current,
            title="Synthetic matrix paper (not a real article)",
            metadata_url="https://example.invalid/synthetic.json",
        )
        decide_row(version, status, family)
        version.save()
        versions.append(version)

    # Every part state under every version state.
    sections = Section.objects.bulk_create(
        Section(version=v, stable_id="body", kind="body", position=0) for v in versions
    )
    figures: list[Figure] = []
    paragraphs: list[Paragraph] = []
    for version, section in zip(versions, sections, strict=True):
        for i, (status, family) in enumerate(itertools.product(STATUSES, FAMILIES)):
            figure = Figure(
                version=version, stable_id=f"fig{i}", kind=Figure.Kind.FIGURE, position=i
            )
            decide_row(figure, status, family)
            figures.append(figure)
            paragraph = Paragraph(
                version=version,
                section=section,
                stable_id=f"body-p{i}",
                kind="p",
                text="Synthetic paragraph.",
                text_sha256="0",
                position=i,
            )
            decide_row(paragraph, status, family)
            paragraphs.append(paragraph)
    Figure.objects.bulk_create(figures)
    Paragraph.objects.bulk_create(paragraphs)
    return versions


def test_matrix_covers_both_outcomes(matrix: list[PaperVersion]) -> None:
    """The matrix is meaningful: some rows pass and many fail."""
    displayable = [v for v in matrix if version_display_ok(v)]
    assert 0 < len(displayable) < len(matrix)
    assert Figure.objects.count() == len(matrix) * len(STATUSES) * len(FAMILIES)


def test_versions_and_papers_match_the_rules_exactly(matrix: list[PaperVersion]) -> None:
    """displayable()/rewriteable() return exactly the versions and papers that pass."""
    by_pk = {v.pk: v for v in matrix}
    assert set(PaperVersion.objects.displayable().values_list("pk", flat=True)) == {
        pk for pk, v in by_pk.items() if version_display_ok(v)
    }
    assert set(PaperVersion.objects.rewriteable().values_list("pk", flat=True)) == {
        pk for pk, v in by_pk.items() if version_rewrite_ok(v)
    }
    assert set(Paper.objects.displayable().values_list("pk", flat=True)) == {
        v.paper_id for v in matrix if version_display_ok(v)
    }
    assert set(Paper.objects.rewriteable().values_list("pk", flat=True)) == {
        v.paper_id for v in matrix if version_rewrite_ok(v)
    }
    assert set(access.displayable_papers()) == set(Paper.objects.displayable())


@pytest.mark.parametrize("model", [Figure, Paragraph])
def test_parts_match_the_rules_exactly(
    matrix: list[PaperVersion], model: type[Figure] | type[Paragraph]
) -> None:
    """Figures, tables and paragraphs pass only if they and their version pass."""
    versions = {v.pk: v for v in matrix}
    rows: list[Figure | Paragraph] = list(model.objects.all())
    expected_display = {
        r.pk
        for r in rows
        if own_ok(r.gate_status, r.licence_family) and version_display_ok(versions[r.version_id])
    }
    expected_rewrite = {
        r.pk
        for r in rows
        if own_rewrite_ok(r.gate_status, r.licence_family)
        and version_rewrite_ok(versions[r.version_id])
    }
    assert set(model.objects.displayable().values_list("pk", flat=True)) == expected_display
    assert set(model.objects.rewriteable().values_list("pk", flat=True)) == expected_rewrite
    assert expected_display, "some parts must pass for the comparison to mean anything"


def test_no_returned_figure_fails_its_own_override(matrix: list[PaperVersion]) -> None:
    """A figure whose own override refuses it is never displayable, even in an open paper."""
    for figure in Figure.objects.displayable().select_related("version"):
        assert figure.gate_status == GateStatus.APPROVED
        assert Licence(LicenceFamily(figure.licence_family)).is_open
        assert figure.version.is_current
        assert figure.version.can_display
    closed = Figure.objects.filter(
        version__in=[v for v in matrix if version_display_ok(v)]
    ).exclude(gate_status=GateStatus.APPROVED)
    assert closed.exists()
    assert not Figure.objects.displayable().filter(pk__in=closed).exists()


def test_access_layer_applies_the_gate_per_version(matrix: list[PaperVersion]) -> None:
    """Access helpers return nothing for a failing version, and only passing parts otherwise."""
    for version in matrix:
        paragraphs = list(access.displayable_paragraphs(version))
        figures = list(access.displayable_figures(version))
        sections = list(access.displayable_sections(version))
        if not version_display_ok(version):
            assert (paragraphs, figures, sections) == ([], [], [])
            assert access.displayable_version(version.paper) is None
            continue
        assert access.displayable_version(version.paper) == version
        assert all(own_ok(p.gate_status, p.licence_family) for p in paragraphs)
        assert all(own_ok(f.gate_status, f.licence_family) for f in figures)
        rewriteable = list(access.rewriteable_paragraphs(version))
        if not version_rewrite_ok(version):
            assert rewriteable == []
        assert all(own_rewrite_ok(p.gate_status, p.licence_family) for p in rewriteable)
        assert [p.position for p in paragraphs] == sorted(p.position for p in paragraphs)
