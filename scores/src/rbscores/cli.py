"""The ``rbscores`` command line.

Commands::

    rbscores score PATH [--json] [--top-terms N] [--no-paragraphs]
    rbscores terms PATH [--limit N] [--json]
    rbscores validation1 download [--data-dir DIR] [--sources elife plos] [--calibration-rows N]
    rbscores validation1 calibrate --output FILE --version NAME [--data-dir DIR]
    rbscores validation1 run [--data-dir DIR] [--reference FILE] [--limit N]
                             [--output FILE] [--markdown FILE]
    rbscores human validate {pairwise,marks} FILE
    rbscores human evaluate {pairwise,marks} FILE    (prints JSON)

``PATH`` is a JATS XML file (``.xml``/``.nxml``) or a UTF-8 text file. Every
score output is PROVISIONAL and says so.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TextIO

from rbcore.config import Settings
from rbcore.jats import JatsParseError
from rbscores.human_data import marks, pairwise
from rbscores.human_data.common import HumanDataError
from rbscores.nlp import ModelNotInstalledError
from rbscores.scoring import (
    ScoreReport,
    UnitScore,
    rank_undefined_terms,
    score_document,
    term_to_dict,
)
from rbscores.status import PROVISIONAL_NOTICE
from rbscores.text import load_document
from rbscores.validation1 import workflow
from rbscores.validation1.dataset import DATASETS
from rbscores.validation1.render import render_medians, render_tables


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        The parser with every subcommand.
    """
    parser = argparse.ArgumentParser(
        prog="rbscores",
        description="PROVISIONAL readability and prior-knowledge burden scores (Track R).",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    # Scoring a file.
    score = commands.add_parser("score", help="score a JATS XML or text file")
    score.add_argument("path", type=Path)
    score.add_argument("--json", action="store_true", help="print the full report as JSON")
    score.add_argument("--top-terms", type=int, default=10, help="ranked terms per unit")
    score.add_argument("--no-paragraphs", action="store_true", help="omit paragraph scores")

    terms = commands.add_parser("terms", help="rank a file's undefined, unfamiliar terms")
    terms.add_argument("path", type=Path)
    terms.add_argument("--limit", type=int, default=30)
    terms.add_argument("--json", action="store_true")

    # Validation 1.
    validation = commands.add_parser("validation1", help="lay summary vs abstract validation")
    steps = validation.add_subparsers(dest="step", required=True)
    download = steps.add_parser("download", help="download pairs and calibration text")
    download.add_argument("--data-dir", type=Path)
    download.add_argument(
        "--sources", nargs="+", choices=sorted(DATASETS), default=sorted(DATASETS)
    )
    download.add_argument("--calibration-rows", type=int, default=workflow.DEFAULT_CALIBRATION_ROWS)
    calibrate = steps.add_parser("calibrate", help="compute the composite's reference statistics")
    calibrate.add_argument("--data-dir", type=Path)
    calibrate.add_argument("--output", type=Path, required=True)
    calibrate.add_argument("--version", required=True, help="version string to record")
    run = steps.add_parser("run", help="score every pair and summarise")
    run.add_argument("--data-dir", type=Path)
    run.add_argument("--reference", type=Path, help="reference JSON (default: packaged)")
    run.add_argument("--sources", nargs="+", choices=sorted(DATASETS), default=sorted(DATASETS))
    run.add_argument("--limit", type=int, help="at most this many pairs per corpus")
    run.add_argument("--output", type=Path, help="write the results JSON here")
    run.add_argument("--markdown", type=Path, help="write the markdown tables here")

    # Human data (validation 2 and the burden validation).
    human = commands.add_parser("human", help="validate or evaluate human study data")
    actions = human.add_subparsers(dest="action", required=True)
    for action in ("validate", "evaluate"):
        sub = actions.add_parser(action)
        sub.add_argument("kind", choices=["pairwise", "marks"])
        sub.add_argument("path", type=Path)
    return parser


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None) -> int:
    """Run the command line.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).
        out: Where to write output (defaults to ``sys.stdout``).

    Returns:
        The exit status: 0 on success, 1 for invalid or missing input (with a
        one-line message on standard error) or invalid human study data.
    """
    args = build_parser().parse_args(argv)
    stream = out or sys.stdout
    try:
        return _dispatch(args, stream)
    except (FileNotFoundError, UnicodeDecodeError, ValueError, ModelNotInstalledError) as exc:
        sys.stderr.write(f"rbscores: {_error_message(args, exc)}\n")
        return 1


def _dispatch(args: argparse.Namespace, out: TextIO) -> int:
    """Run the chosen command.

    Args:
        args: Parsed arguments.
        out: Output stream.

    Returns:
        The command's exit status.
    """
    if args.command == "score":
        return _score(args, out)
    if args.command == "terms":
        return _terms(args, out)
    if args.command == "validation1":
        return _validation1(args, out)
    return _human(args, out)


def _error_message(args: argparse.Namespace, exc: Exception) -> str:
    """Describe an expected user error in one line.

    Args:
        args: Parsed arguments (to name the input and give a hint).
        exc: The error.

    Returns:
        The message, without a trailing newline.
    """
    # A missing file under validation 1's data directory means the download
    # step has not been run there.
    if isinstance(exc, FileNotFoundError):
        missing = str(exc.filename or _input_path(args))
        if args.command == "validation1":
            data_dir = workflow.validation_dir(args.data_dir or Settings.from_env().data_dir)
            if Path(missing).resolve().is_relative_to(data_dir.resolve()):
                return f"{missing} not found; run `rbscores validation1 download` first"
        return f"{missing}: no such file"

    # Input that exists but cannot be used as given.
    if isinstance(exc, UnicodeDecodeError):
        return f"{_input_path(args)} is not UTF-8 text ({exc.reason} at byte {exc.start})"
    if isinstance(exc, JatsParseError):
        return f"{_input_path(args)} is not usable JATS XML: {exc}"
    return str(exc)


def _input_path(args: argparse.Namespace) -> str:
    """Return the input path named on the command line, if any.

    Args:
        args: Parsed arguments.

    Returns:
        The ``path`` argument, or "input" when the command has none.
    """
    path = getattr(args, "path", None)
    return str(path) if path is not None else "input"


def _score(args: argparse.Namespace, out: TextIO) -> int:
    """Score a file and print the report.

    Args:
        args: Parsed arguments.
        out: Output stream.

    Returns:
        0.
    """
    report = score_document(load_document(args.path))
    if args.json:
        data = report.to_dict(top_terms=args.top_terms, paragraphs=not args.no_paragraphs)
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return 0
    _write_text_report(report, out, top_terms=args.top_terms, paragraphs=not args.no_paragraphs)
    return 0


def _write_text_report(
    report: ScoreReport, out: TextIO, *, top_terms: int, paragraphs: bool
) -> None:
    """Print a human-readable report.

    Args:
        report: The score report.
        out: Output stream.
        top_terms: Ranked terms to show for the paper.
        paragraphs: Also list paragraph scores.
    """
    out.write(f"{PROVISIONAL_NOTICE}\n\n")
    out.write(f"Document: {report.title or report.identifier or '(untitled)'}\n")
    out.write(f"Model: {report.model}; reference: {report.reference_version}\n\n")
    out.write(f"{'unit':<16} {'words':>6} {'composite':>10} {'burden/1k':>10}\n")
    units = [report.paper, *report.sections, *(report.paragraphs if paragraphs else ())]
    for unit in units:
        out.write(_unit_line(unit))
    out.write(
        f"\nTop undefined terms in the paper (of {len(report.paper.burden.undefined_terms)}):\n"
    )
    for term in report.paper.burden.undefined_terms[:top_terms]:
        out.write(f"  {term.weight:.2f}  x{term.count:<3} {term.text}\n")


def _unit_line(unit: UnitScore) -> str:
    """Format one unit's scores as a table row.

    Args:
        unit: The unit's scores.

    Returns:
        The row, newline-terminated.
    """
    label = unit.id if unit.level != "paper" else "PAPER"
    composite = f"{unit.composite:.2f}" if unit.composite is not None else "-"
    return (
        f"{label:<16} {unit.burden.words:>6} {composite:>10} {unit.burden.burden_per_1000:>10.1f}\n"
    )


def _terms(args: argparse.Namespace, out: TextIO) -> int:
    """Print a file's ranked undefined terms.

    Args:
        args: Parsed arguments.
        out: Output stream.

    Returns:
        0.
    """
    ranked = rank_undefined_terms(load_document(args.path), limit=args.limit)
    if args.json:
        data: dict[str, Any] = {
            "notice": PROVISIONAL_NOTICE,
            "terms": [term_to_dict(t) for t in ranked],
        }
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return 0
    out.write(f"{PROVISIONAL_NOTICE}\n\n")
    for term in ranked:
        where = ", ".join(sorted({loc.paragraph_id for loc in term.locations}))
        out.write(f"{term.weight:.2f}  x{term.count:<3} {term.text}  [{where}]\n")
    return 0


def _validation1(args: argparse.Namespace, out: TextIO) -> int:
    """Run one validation 1 step.

    Args:
        args: Parsed arguments.
        out: Output stream (progress and tables).

    Returns:
        0.
    """
    data_dir = args.data_dir or Settings.from_env().data_dir

    def log(message: str) -> None:
        """Write a progress line to standard error."""
        sys.stderr.write(message + "\n")

    if args.step == "download":
        workflow.download(
            data_dir, sources=args.sources, calibration_rows=args.calibration_rows, log=log
        )
        return 0
    if args.step == "calibrate":
        reference = workflow.calibrate(data_dir, args.output, version=args.version)
        out.write(json.dumps(reference.to_json(), indent=2) + "\n")
        return 0

    # The run step: results JSON and markdown tables.
    results = workflow.run(
        data_dir, reference_path=args.reference, sources=args.sources, limit=args.limit, log=log
    )
    tables = (
        render_tables(results) + "\n#### Median values (full texts)\n\n" + render_medians(results)
    )
    if args.output:
        args.output.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", "utf-8")
    if args.markdown:
        args.markdown.write_text(tables, encoding="utf-8")
    out.write(tables)
    return 0


def _human(args: argparse.Namespace, out: TextIO) -> int:
    """Validate or evaluate a human study file.

    Args:
        args: Parsed arguments.
        out: Output stream.

    Returns:
        0 if the file is valid (and evaluated), 1 if it is not.
    """
    try:
        if args.kind == "pairwise":
            study: Any = pairwise.load_pairwise(args.path)
        else:
            study = marks.load_marks(args.path)
    except HumanDataError as exc:
        out.write(f"INVALID {args.path}:\n")
        for problem in exc.problems:
            out.write(f"  - {problem}\n")
        return 1

    if args.action == "validate":
        out.write(f"OK {args.path}: {study.summary()}\n")
        return 0

    # Evaluation against the PROVISIONAL scores.
    evaluation = (
        pairwise.evaluate_pairwise_with_scores(study)
        if args.kind == "pairwise"
        else marks.evaluate_marks(study)
    )
    data = {"notice": PROVISIONAL_NOTICE, **evaluation}
    out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return 0
