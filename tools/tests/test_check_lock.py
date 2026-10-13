"""Tests for rb_devtools.check_lock."""

from __future__ import annotations

from pathlib import Path

import pytest

from rb_devtools.check_lock import locked_packages, main, missing_from_lock

_LOCK = """\
-e file:tools
    # via -r requirements/packages.in
-e file:libs/rbcore
    # via -r requirements/packages.in
lxml==6.1.3
    # via researchbridge-rbcore
"""


def test_locked_packages_reads_editable_lines_only() -> None:
    """Only ``-e file:`` lines count as locked packages."""
    assert locked_packages(_LOCK) == {"tools", "libs/rbcore"}


def test_missing_from_lock_reports_unlocked_package() -> None:
    """A package directory with no editable line is reported."""
    assert missing_from_lock(["libs/rbcore", "backend/", "tools"], _LOCK) == ["backend"]


def test_main_exit_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI exits 0 when all packages are locked and 1 with a hint otherwise."""
    lock = tmp_path / "dev.txt"
    lock.write_text(_LOCK)
    assert main(["--lock", str(lock), "libs/rbcore", "tools"]) == 0
    assert main(["--lock", str(lock), "benchmark"]) == 1
    assert "run `make lock`" in capsys.readouterr().err
