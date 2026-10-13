"""Tests for rb_devtools.check_docstrings."""

from __future__ import annotations

from pathlib import Path

import pytest

from rb_devtools.check_docstrings import find_missing, iter_python_files, main

_DOCUMENTED = '''"""Module."""


class Thing:
    """A thing."""

    def method(self) -> None:
        """Do it."""

        def inner() -> None:
            """Nested helper."""


def _private() -> None:
    """Private helper."""
'''


def test_fully_documented_source_has_no_findings() -> None:
    """A module where every definition has a docstring passes."""
    assert find_missing(_DOCUMENTED, Path("m.py")) == []


def test_reports_private_nested_and_method_definitions() -> None:
    """Private helpers, nested functions and methods are all checked, unlike pydocstyle."""
    source = (
        '"""Module."""\n'
        "class Thing:\n"
        "    def method(self):\n"
        "        def inner():\n"
        "            pass\n"
        "def _private():\n"
        "    pass\n"
    )
    findings = find_missing(source, Path("m.py"))
    assert [(f.kind, f.name, f.line) for f in findings] == [
        ("class", "Thing", 2),
        ("function", "Thing.method", 3),
        ("function", "Thing.method.inner", 4),
        ("function", "_private", 6),
    ]


def test_reports_missing_module_docstring_but_not_for_empty_file() -> None:
    """A non-empty module needs a docstring; an empty file does not."""
    assert [f.kind for f in find_missing("x = 1\n", Path("m.py"))] == ["module"]
    assert find_missing("", Path("__init__.py")) == []


def test_definitions_inside_blocks_are_found() -> None:
    """Functions defined under if/try blocks are still checked."""
    source = '"""M."""\nif True:\n    def hidden():\n        pass\n'
    assert [f.name for f in find_missing(source, Path("m.py"))] == ["hidden"]


def test_finding_formats_as_path_line_message() -> None:
    """The string form points an editor at the definition."""
    (finding,) = find_missing('"""M."""\ndef f():\n    pass\n', Path("pkg/m.py"))
    assert str(finding) == "pkg/m.py:2: missing docstring on function f"


def test_excluded_paths_are_skipped(tmp_path: Path) -> None:
    """Generated Django migrations are excluded by pattern."""
    (tmp_path / "app" / "migrations").mkdir(parents=True)
    (tmp_path / "app" / "migrations" / "0001_initial.py").write_text("x = 1\n")
    (tmp_path / "app" / "models.py").write_text('"""Models."""\n')
    files = list(iter_python_files([tmp_path], ["*/migrations/*.py"]))
    assert [p.name for p in files] == ["models.py"]


def test_main_returns_nonzero_and_reports(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The CLI exits 1 and lists each finding on stderr."""
    (tmp_path / "bad.py").write_text('"""M."""\ndef f():\n    pass\n')
    assert main([str(tmp_path)]) == 1
    assert "missing docstring on function f" in capsys.readouterr().err


def test_main_returns_zero_when_clean(tmp_path: Path) -> None:
    """The CLI exits 0 when everything is documented."""
    (tmp_path / "good.py").write_text(_DOCUMENTED)
    assert main([str(tmp_path)]) == 0
