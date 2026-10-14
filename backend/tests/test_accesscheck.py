"""The static gate check flags bypasses and passes the real code base."""

from __future__ import annotations

from pathlib import Path

import pytest

import rb_backend
from rb_backend.corpus.accesscheck import check_package, find_violations, is_trusted

PACKAGE = Path(rb_backend.__file__).parent


@pytest.mark.parametrize(
    "source",
    [
        "Paper.objects.all()",
        "Paragraph.objects.filter(version=v)",
        "Figure.objects.get(pk=1)",
        "PaperVersion.objects.first()",
        "Annotation.objects.all()",
        "SearchDocument.objects.filter(document=query)",
        "version.paragraphs.all()",
        "paper.versions.filter(is_current=True)",
        "version.figures.first()",
        "paper.current_version",
        "Paper._default_manager.all()",
        "Paper.objects.raw('select * from corpus_paper')",
        "connection.cursor()",
        "connections['default'].cursor()",
    ],
)
def test_bypasses_are_flagged(source: str) -> None:
    """Each synthetic read path that skips the gate produces one violation."""
    violations = find_violations(source, Path("synthetic_view.py"))
    assert len(violations) == 1
    assert violations[0].line == 1


@pytest.mark.parametrize(
    "source",
    [
        "Paper.objects.displayable()",
        "Paper.objects.rewriteable().filter(doi='x')",
        "Paragraph.objects.displayable().filter(version=v).order_by('position')",
        "version.paragraphs.displayable()",
        "access.displayable_figures(version)",
        "SearchDocument.objects.displayable().filter(document=query)",
        "User.objects.all()",
        "something.objects.all()",
    ],
)
def test_gated_reads_and_unrelated_models_pass(source: str) -> None:
    """Gated methods, the access module and non-corpus models are fine."""
    assert find_violations(source, Path("synthetic_view.py")) == []


def test_violation_reports_path_and_line() -> None:
    """Findings say where they are."""
    (violation,) = find_violations("x = 1\nPaper.objects.all()\n", Path("api/views.py"))
    assert str(violation).startswith("api/views.py:2: Paper.objects.all bypasses")


@pytest.mark.parametrize(
    ("path", "trusted"),
    [
        ("corpus/gate.py", True),
        ("ingestion/pipeline.py", True),
        ("annotations/models.py", True),
        ("annotations/migrations/0001_initial.py", True),
        ("annotations/api.py", False),
        ("reader/views.py", False),
        ("urls.py", False),
    ],
)
def test_trusted_paths(path: str, trusted: bool) -> None:
    """Only gate internals, ingestion, annotation models/admin and migrations are exempt."""
    assert is_trusted(path) is trusted


def test_backend_has_no_gate_bypasses() -> None:
    """The real backend passes: every untrusted module reads through the gate."""
    assert check_package(PACKAGE) == []


def test_check_package_finds_a_planted_bypass(tmp_path: Path) -> None:
    """A new untrusted module that bypasses the gate fails the check."""
    (tmp_path / "reader").mkdir()
    (tmp_path / "reader" / "views.py").write_text("def view():\n    return Paper.objects.all()\n")
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus" / "gate.py").write_text("Paper.objects.all()\n")
    violations = check_package(tmp_path)
    assert [(v.path.name, v.line) for v in violations] == [("views.py", 2)]
