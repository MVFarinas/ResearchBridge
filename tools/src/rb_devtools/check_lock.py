"""Check that every discovered Python package is installed by the lock file.

``make lock`` writes one ``-e file:<dir>`` line per package into
requirements/packages.in and compiles requirements/dev.txt from it. A package
added without re-running ``make lock`` would be silently missing from
``make setup`` and from CI, so ``make lint`` runs this check.

Usage:
    rb-check-lock --lock requirements/dev.txt PACKAGE_DIR [PACKAGE_DIR ...]
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

_EDITABLE_PREFIX = "-e file:"


def locked_packages(lock_text: str) -> set[str]:
    """Return the package directories installed as editables by a lock file.

    Args:
        lock_text: Contents of a pip-compile output file.

    Returns:
        Directory paths as written after ``-e file:``, without trailing slashes.
    """
    found: set[str] = set()
    for line in lock_text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_EDITABLE_PREFIX):
            found.add(stripped.removeprefix(_EDITABLE_PREFIX).rstrip("/"))
    return found


def missing_from_lock(packages: Iterable[str], lock_text: str) -> list[str]:
    """List the package directories that the lock file does not install.

    Args:
        packages: Package directories relative to the repository root.
        lock_text: Contents of the lock file.

    Returns:
        Sorted directories absent from the lock; empty when all are present.
    """
    locked = locked_packages(lock_text)
    return sorted(p.rstrip("/") for p in packages if p.rstrip("/") not in locked)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check from the command line.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when every package is locked, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lock", type=Path, required=True, help="pip-compile output file")
    parser.add_argument("packages", nargs="+", help="package directories")
    args = parser.parse_args(argv)

    missing = missing_from_lock(args.packages, args.lock.read_text(encoding="utf-8"))
    for package in missing:
        sys.stderr.write(f"{package} is not in {args.lock}; run `make lock` and commit it\n")
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
