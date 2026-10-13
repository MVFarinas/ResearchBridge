"""Static check that reader-facing code never bypasses the licence gate.

The gate is only as strong as its weakest read path. Django makes it easy to
write ``Paper.objects.all()`` or ``version.paragraphs.all()`` in a future view
and serve something the gate refused. This module walks the AST of every
backend module outside the trusted internals and reports any read of a gated
model that does not go through ``displayable()`` or ``rewriteable()``:

* ``<GatedModel>.objects.<method>`` for any method other than the two;
* ``<anything>.<gated relation>.<method>`` (``versions``, ``sections``,
  ``paragraphs``, ``figures``, ``annotations``, ``children``) likewise;
* ``_default_manager`` / ``_base_manager`` on a gated model;
* ``.current_version`` (an unrestricted convenience for internal code);
* raw SQL: ``.raw(...)`` on a manager and ``connection.cursor()``.

Trusted internals (the corpus app itself, ingestion, the annotation models
and admin, migrations) are exempt: they write the gate or moderate it. The
test suite runs :func:`check_package` over ``rb_backend``, so new modules in
later phases are checked automatically. It is a guard against mistakes, not a
sandbox: code that deliberately evades it (``getattr`` tricks) is out of
scope for a static check.
"""

from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

GATED_MODELS = frozenset({"Paper", "PaperVersion", "Section", "Paragraph", "Figure", "Annotation"})
GATED_RELATIONS = frozenset(
    {"versions", "sections", "paragraphs", "figures", "annotations", "children"}
)
ALLOWED_METHODS = frozenset({"displayable", "rewriteable"})
UNRESTRICTED_MANAGERS = frozenset({"_default_manager", "_base_manager"})

# Paths (relative to the rb_backend package, POSIX style) that may read
# gated models directly because they implement or moderate the gate.
TRUSTED_PATTERNS: tuple[str, ...] = (
    "corpus/*",
    "ingestion/*",
    "annotations/models.py",
    "annotations/admin.py",
    "*/migrations/*",
)


@dataclass(frozen=True, slots=True)
class Violation:
    """One read of a gated model that bypasses the gate.

    Attributes:
        path: The file.
        line: 1-based line number.
        message: What was found.
    """

    path: Path
    line: int
    message: str

    def __str__(self) -> str:
        """Format as ``path:line: message``."""
        return f"{self.path}:{self.line}: {self.message}"


def find_violations(source: str, path: Path) -> list[Violation]:
    """Find gate-bypassing reads in one module's source.

    Args:
        source: Python source text.
        path: Path to report (not read).

    Returns:
        Violations in source order.

    Raises:
        SyntaxError: If the source does not parse.
    """
    tree = ast.parse(source, filename=str(path))
    found = [Violation(path, line, message) for line, message in _scan(tree)]
    return sorted(found, key=lambda v: v.line)


def _scan(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """Yield ``(line, message)`` for every suspicious attribute access.

    Args:
        tree: A parsed module.

    Yields:
        One pair per violation.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        owner = node.value
        # Model.objects.<method>: only the gated methods are allowed.
        if (
            isinstance(owner, ast.Attribute)
            and owner.attr == "objects"
            and _name(owner.value) in GATED_MODELS
            and node.attr not in ALLOWED_METHODS
        ):
            if node.attr == "raw":
                yield node.lineno, f"raw SQL on {_name(owner.value)}.objects"
            else:
                yield (
                    node.lineno,
                    (
                        f"{_name(owner.value)}.objects.{node.attr} bypasses the licence gate; "
                        "use displayable() or rewriteable()"
                    ),
                )
        # <obj>.<gated relation>.<method>: related managers need the gate too.
        elif (
            isinstance(owner, ast.Attribute)
            and owner.attr in GATED_RELATIONS
            and node.attr not in ALLOWED_METHODS
        ):
            yield (
                node.lineno,
                (
                    f".{owner.attr}.{node.attr} bypasses the licence gate; "
                    "use displayable() or rewriteable()"
                ),
            )
        # Unrestricted managers and the internal current_version shortcut.
        elif node.attr in UNRESTRICTED_MANAGERS and _name(owner) in GATED_MODELS:
            yield node.lineno, f"{_name(owner)}.{node.attr} bypasses the licence gate"
        elif node.attr == "current_version":
            yield (
                node.lineno,
                (
                    ".current_version is unrestricted; "
                    "use rb_backend.corpus.access.displayable_version"
                ),
            )
        # Raw database cursors can read anything.
        elif (node.attr == "cursor" and _name(owner) in {"connection", "connections"}) or (
            node.attr == "cursor"
            and isinstance(owner, ast.Subscript)
            and _name(owner.value) == "connections"
        ):
            yield node.lineno, "raw database cursor bypasses the licence gate"


def _name(node: ast.expr) -> str | None:
    """Return the identifier of a bare name node.

    Args:
        node: An expression.

    Returns:
        The name, or None if the node is not a plain name.
    """
    return node.id if isinstance(node, ast.Name) else None


def is_trusted(relative: str, patterns: Sequence[str] = TRUSTED_PATTERNS) -> bool:
    """Whether a module path is exempt from the check.

    Args:
        relative: Path relative to the package root, POSIX style.
        patterns: Glob patterns of trusted paths.

    Returns:
        True if any pattern matches.
    """
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def check_package(root: Path, patterns: Sequence[str] = TRUSTED_PATTERNS) -> list[Violation]:
    """Check every untrusted module under a package directory.

    Args:
        root: The package directory (``rb_backend``).
        patterns: Glob patterns of trusted paths.

    Returns:
        All violations, sorted by path and line.
    """
    violations: list[Violation] = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        if is_trusted(relative, patterns):
            continue
        violations.extend(find_violations(path.read_text(encoding="utf-8"), path))
    return violations
