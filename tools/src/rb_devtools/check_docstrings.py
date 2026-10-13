"""Check that every module, class, function and method has a docstring.

Ruff's pydocstyle rules only cover public names. The project conventions
(docs/conventions.md) require a docstring on private helpers, nested functions
and test functions too, so this check walks the AST of every Python file and
reports each definition without one.

Usage:
    rb-check-docstrings DIR [DIR ...]
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

# Generated or third-party code that is exempt from the rule.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    "*/migrations/*.py",
    "*/third_party/*",
    "*/.venv/*",
    "*/node_modules/*",
    "*/build/*",
)

_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True, slots=True)
class MissingDocstring:
    """One definition that lacks a docstring.

    Attributes:
        path: File containing the definition.
        line: 1-based line number of the definition (1 for a module).
        kind: "module", "class" or "function".
        name: Qualified name within the file, e.g. "Parser._helper".
    """

    path: Path
    line: int
    kind: str
    name: str

    def __str__(self) -> str:
        """Format the finding as ``path:line: missing docstring on kind name``."""
        return f"{self.path}:{self.line}: missing docstring on {self.kind} {self.name}"


def find_missing(source: str, path: Path) -> list[MissingDocstring]:
    """Find every definition in one source file that has no docstring.

    Args:
        source: The Python source text.
        path: Path used in the findings (not read from disk).

    Returns:
        Findings in source order; empty when every definition is documented.

    Raises:
        SyntaxError: If the source does not parse.
    """
    tree = ast.parse(source, filename=str(path))
    findings: list[MissingDocstring] = []

    # An empty file (for example a bare __init__.py placeholder) has nothing to document.
    if tree.body and ast.get_docstring(tree) is None:
        findings.append(MissingDocstring(path, 1, "module", path.stem))

    findings.extend(_walk(tree, path, prefix=""))
    return findings


def _walk(node: ast.AST, path: Path, prefix: str) -> Iterator[MissingDocstring]:
    """Yield missing-docstring findings for definitions nested under ``node``.

    Args:
        node: The AST node whose children are inspected.
        path: File path for the findings.
        prefix: Qualified-name prefix of ``node`` ("" at module level).

    Yields:
        One finding per undocumented class or function, depth first.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _DEFINITIONS):
            name = f"{prefix}{child.name}"
            if ast.get_docstring(child) is None:
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                yield MissingDocstring(path, child.lineno, kind, name)
            yield from _walk(child, path, prefix=f"{name}.")
        else:
            # Definitions can sit inside if/try/with blocks; keep the same prefix.
            yield from _walk(child, path, prefix=prefix)


def iter_python_files(roots: Sequence[Path], excludes: Sequence[str]) -> Iterator[Path]:
    """Yield the Python files under ``roots``, skipping excluded patterns.

    Args:
        roots: Files or directories to scan.
        excludes: fnmatch patterns matched against each file's POSIX path
            (prefixed with "./" so a leading "*/" also matches top-level dirs).

    Yields:
        Paths of ``.py`` files in sorted order.
    """
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in candidates:
            posix = path.as_posix() if path.is_absolute() else f"./{path.as_posix()}"
            if not any(fnmatch.fnmatch(posix, pattern) for pattern in excludes):
                yield path


def main(argv: Sequence[str] | None = None) -> int:
    """Run the check from the command line.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        0 when every definition is documented, 1 otherwise.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("roots", nargs="+", type=Path, help="files or directories to check")
    parser.add_argument(
        "--exclude",
        action="append",
        default=list(DEFAULT_EXCLUDES),
        help="extra fnmatch pattern to skip (repeatable)",
    )
    args = parser.parse_args(argv)

    findings: list[MissingDocstring] = []
    for path in iter_python_files(args.roots, args.exclude):
        findings.extend(find_missing(path.read_text(encoding="utf-8"), path))

    # Report every finding at once so a contributor can fix them in one pass.
    for finding in findings:
        sys.stderr.write(f"{finding}\n")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
