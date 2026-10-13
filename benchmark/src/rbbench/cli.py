"""The ``rbbench`` command line: one subcommand per benchmark step.

Run ``rbbench <command> --help`` for the options. Outputs go to the gitignored
data directory (``<RB_DATA_DIR>/benchmark``) unless a path is given; the
candidate shortlist goes to ``benchmark/selection/`` because it is committed
for the owner to review.

Real LLM calls need ``--client anthropic --live`` and an ``ANTHROPIC_API_KEY``;
everything else runs offline with ``--client fake`` (the default).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from rbbench import baselines, comprehension
from rbbench.agreement import (
    FinalLabel,
    Policy,
    agreement_report,
    finals_as_ratings,
    format_agreement_table,
    merge_labels,
    read_adjudications,
    write_disagreements,
)
from rbbench.attribution import AttributionError, attribution_line
from rbbench.claims import Claim, Method, decompose
from rbbench.clients import ClientKind, LiveCallsNotAllowedError, make_client
from rbbench.dryrun import run_dry_run
from rbbench.ingest import (
    PAPERS_FILE,
    LicenceGateError,
    gate_violations,
    ingest_paper,
    load_passages,
    load_units,
    load_usable_papers,
    write_ingest,
)
from rbbench.jsonl import read_jsonl, write_json, write_jsonl
from rbbench.judge import factpico
from rbbench.judge.harness import build_items, judge_items
from rbbench.packets.build import PacketError, build_packets
from rbbench.packets.importer import import_ratings, load_key
from rbbench.paths import CONFIG_DIR, RBCORE_FIXTURES_DIR, SELECTION_DIR, data_root
from rbbench.ratings import load_ratings, save_ratings
from rbbench.rewrite.harness import RewriteRecord, load_matrix, run_rewrites
from rbbench.rubric import load_rubric
from rbbench.selection.config import load_selection_config
from rbbench.selection.shortlist import (
    build_shortlist,
    read_candidates,
    write_candidates,
    write_pool_log,
    write_screening_log,
)
from rbbench.sources.eutils import EutilsClient
from rbbench.sources.papers import candidate_sources, fixture_sources
from rbcore.config import ConfigError, Settings
from rbcore.http import PoliteFetcher

Handler = Callable[[argparse.Namespace], int]


class UsageError(Exception):
    """Raised by a command for a user-fixable problem; reported without a traceback."""


@dataclass(frozen=True, slots=True)
class _DataDefault:
    """A default path inside the data directory, resolved only when a command runs.

    Resolving lazily keeps ``rbbench --help`` working when the environment's
    settings are invalid (the error then comes from the command, cleanly).

    Attributes:
        relative: Path relative to ``<RB_DATA_DIR>/benchmark``.
    """

    relative: str

    def __str__(self) -> str:
        """Return the path as shown in help text.

        Returns:
            ``<RB_DATA_DIR>/benchmark/<relative>``.
        """
        return f"<RB_DATA_DIR>/benchmark/{self.relative}"


def _resolve_data_defaults(args: argparse.Namespace) -> None:
    """Replace every unresolved data-directory default with a real path.

    Args:
        args: Parsed arguments, updated in place.

    Raises:
        rbcore.config.ConfigError: If the environment's settings are invalid.
    """
    defaults = {k: v for k, v in vars(args).items() if isinstance(v, _DataDefault)}
    if defaults:
        root = data_root()
        for name, default in defaults.items():
            setattr(args, name, root / default.relative)


def _say(message: str) -> None:
    """Write one progress or result line to standard error.

    Args:
        message: The line.
    """
    sys.stderr.write(f"{message}\n")


def _fetcher(settings: Settings) -> PoliteFetcher:
    """Build the polite fetcher with its cache in the data directory.

    Args:
        settings: Runtime settings.

    Returns:
        The fetcher.
    """
    return PoliteFetcher(cache_dir=data_root(settings) / "cache", user_agent=settings.user_agent)


def _load_rewrites(path: Path) -> list[RewriteRecord]:
    """Read rewrite records.

    Args:
        path: rewrites JSONL.

    Returns:
        The records.
    """
    return [RewriteRecord.from_record(r) for r in read_jsonl(path)]


def _require_ingest(ingest: Path) -> None:
    """Check that an ingest directory exists before a command relies on it.

    Args:
        ingest: The ingest directory.

    Raises:
        UsageError: If its papers file is missing.
    """
    if not (ingest / PAPERS_FILE).is_file():
        raise UsageError(f"no {PAPERS_FILE} in {ingest}: run `rbbench ingest` or pass --ingest")


def _require_gated_rewrites(rewrites: Sequence[RewriteRecord], ingest: Path) -> None:
    """Re-apply the §1.1 gate to rewrites before their source text is shown or sent.

    Defence in depth: rewrites are gated when generated, but a rewrites file
    could have been produced from an edited ingest or another directory.

    Args:
        rewrites: The rewrites.
        ingest: The ingest directory they came from.

    Raises:
        UsageError: If the ingest directory is missing.
        rbbench.ingest.LicenceGateError: Listing every rewrite over refused text.
    """
    _require_ingest(ingest)
    units, usable = load_units(ingest), load_usable_papers(ingest)
    violations = [
        f"{rewrite.rewrite_id}: {message}"
        for rewrite in rewrites
        for message in gate_violations(
            rewrite.paper_key, [pid for pid, _ in rewrite.source], units, usable
        )
    ]
    if violations:
        raise LicenceGateError("licence gate (§1.1) refused: " + "; ".join(violations))


def _load_claims(path: Path) -> list[Claim]:
    """Read claims.

    Args:
        path: claims JSONL.

    Returns:
        The claims.
    """
    return [Claim.from_record(r) for r in read_jsonl(path)]


def cmd_select(args: argparse.Namespace) -> int:
    """Build the PROPOSED candidate shortlist (network; polite and cached).

    Args:
        args: Parsed arguments.

    Returns:
        Exit status (1 if some slot is unfilled).
    """
    settings = Settings.from_env()
    config = load_selection_config(args.config)
    with _fetcher(settings) as fetcher:
        shortlist = build_shortlist(
            config, EutilsClient(fetcher, settings.ncbi_api_key), fetcher, progress=_say
        )
    write_candidates(args.out_dir / "candidates.csv", shortlist.candidates)
    write_screening_log(args.out_dir / "screening_log.csv", shortlist.screening)
    write_pool_log(args.out_dir / "pool_log.csv", shortlist.pools)
    _say(f"{len(shortlist.candidates)} candidates written to {args.out_dir / 'candidates.csv'}")
    if shortlist.unfilled:
        _say(f"unfilled slots: {', '.join(shortlist.unfilled)}")
        return 1
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    """Fetch and parse papers into units and proposed passages.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.
    """
    settings = Settings.from_env()
    if args.fixtures:
        if args.only:
            raise UsageError(
                "--only selects shortlist candidates; it cannot be used with --fixtures"
            )
        sources = fixture_sources(RBCORE_FIXTURES_DIR)
    else:
        candidates = read_candidates(args.candidates)
        # --only must match something, and every name given must match, or nothing is written.
        if args.only is not None:
            wanted = {name.strip() for name in args.only.split(",") if name.strip()}
            names = {c: {c.pmcid, c.paper_key, c.slot + c.option} for c in candidates}
            unmatched = wanted.difference(*names.values())
            if not wanted or unmatched:
                raise UsageError(f"--only matches no candidate: {', '.join(sorted(unmatched))}")
            candidates = [c for c in candidates if names[c] & wanted]
        with _fetcher(settings) as fetcher:
            sources = candidate_sources(candidates, fetcher)
    papers = [ingest_paper(s, min_words=args.min_words, max_words=args.max_words) for s in sources]
    write_ingest(args.out, papers)
    for paper in papers:
        passage = paper.passage.passage_id if paper.passage else "no passage"
        state = "usable" if paper.usable else "REFUSED: " + "; ".join(paper.licence_reasons)
        _say(f"{paper.paper_key}: {len(paper.units)} units, {passage}, {state}")
    return 0


def cmd_rewrite(args: argparse.Namespace) -> int:
    """Rewrite every passage in every arm of the matrix.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status (1 if any rewrite is invalid).

    Raises:
        UsageError: If the ingest directory is missing.
        rbbench.ingest.LicenceGateError: If any passage includes text the
            §1.1 gate refused (nothing is sent).
    """
    settings = Settings.from_env()
    _require_ingest(args.ingest)
    client, requested = make_client(
        ClientKind(args.client),
        role="generation",
        settings=settings,
        live=args.live,
        model=args.model,
    )
    papers = {r["paper_key"]: r["title"] for r in read_jsonl(args.ingest / PAPERS_FILE)}
    records = run_rewrites(
        load_passages(args.ingest),
        load_units(args.ingest),
        papers,
        load_matrix(args.matrix),
        client,
        requested_model=requested,
        repeats=args.repeats,
        progress=_say,
        usable_papers=load_usable_papers(args.ingest),
    )
    write_jsonl(args.out, (r.to_record() for r in records))
    invalid = sum(not r.valid for r in records)
    _say(f"{len(records)} rewrites written to {args.out} ({invalid} invalid)")
    return 1 if invalid else 0


def cmd_decompose(args: argparse.Namespace) -> int:
    """Decompose valid rewrites into claims.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.
    """
    method = Method(args.method)
    client = None
    if method is Method.LLM:
        client, _ = make_client(
            ClientKind(args.client),
            role="generation",
            settings=Settings.from_env(),
            live=args.live,
            model=args.model,
        )
    rewrites = [r for r in _load_rewrites(args.rewrites) if r.valid]
    claims = [c for r in rewrites for c in decompose(r, method, client=client)]
    write_jsonl(args.out, (c.to_record() for c in claims))
    _say(f"{len(claims)} claims from {len(rewrites)} valid rewrites written to {args.out}")
    return 0


def cmd_packets(args: argparse.Namespace) -> int:
    """Build per-rater packets and the unblinding key.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.

    Raises:
        UsageError: If the ingest directory is missing.
        rbbench.ingest.LicenceGateError: If a rewrite's source text was refused.
        rbbench.packets.build.PacketError: If the packets cannot be built.
    """
    # Packets show source text verbatim, so it must pass the gate and be attributed.
    rewrites = [r for r in _load_rewrites(args.rewrites) if r.valid]
    _require_gated_rewrites(rewrites, args.ingest)
    papers = {r["paper_key"]: r for r in read_jsonl(args.ingest / PAPERS_FILE)}
    needed = {r.paper_key for r in rewrites}
    paths = build_packets(
        rewrites,
        _load_claims(args.claims),
        load_rubric(),
        args.raters.split(","),
        args.out,
        packet_id=args.packet_id,
        attributions={key: attribution_line(papers[key]) for key in needed},
        titles={key: str(papers[key]["title"]) for key in needed},
    )
    for path in paths:
        _say(f"{path.rater_id}: {path.html}")
    _say(f"keep {args.out / 'key.json'} yourself: it unblinds the packets")
    return 0


def cmd_import(args: argparse.Namespace) -> int:
    """Import rater exports into one ratings file.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.
    """
    rubric = load_rubric()
    key = load_key(args.key)
    ratings = [
        rating
        for export in args.exports
        for rating in import_ratings(export, key, rubric, allow_incomplete=args.allow_incomplete)
    ]
    save_ratings(args.out, ratings)
    _say(f"{len(ratings)} ratings from {len(args.exports)} export(s) written to {args.out}")
    return 0


def cmd_agreement(args: argparse.Namespace) -> int:
    """Report per-code agreement.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.
    """
    ratings = [r for path in args.ratings for r in load_ratings(path)]
    entries = agreement_report(ratings, load_rubric())
    if args.out:
        write_json(args.out, [e.to_record() for e in entries])
    sys.stdout.write(format_agreement_table(entries) + "\n")
    return 0


def cmd_adjudicate(args: argparse.Namespace) -> int:
    """Merge ratings into final labels, applying adjudications if given.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status (1 while disagreements remain unresolved).
    """
    rubric = load_rubric()
    ratings = [r for path in args.ratings for r in load_ratings(path)]
    adjudications = read_adjudications(args.adjudications) if args.adjudications else None
    finals = merge_labels(ratings, rubric, adjudications=adjudications, policy=Policy(args.policy))
    write_jsonl(args.out, (f.to_record() for f in finals))
    unresolved = write_disagreements(args.disagreements, finals, rubric)
    _say(f"{len(finals)} final labels written to {args.out}; {unresolved} unresolved")
    if unresolved:
        _say(f"fill in {args.disagreements} and rerun with --adjudications")
    return 1 if unresolved else 0


def cmd_judge(args: argparse.Namespace) -> int:
    """Run the LLM judge on every claim and paragraph.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status (1 if any judgement is invalid).

    Raises:
        UsageError: If the ingest directory is missing.
        rbbench.ingest.LicenceGateError: If a rewrite's source text was refused.
    """
    # The judge sends source text to a model, so the gate is re-applied first.
    rubric = load_rubric()
    rewrites = [r for r in _load_rewrites(args.rewrites) if r.valid]
    _require_gated_rewrites(rewrites, args.ingest)
    client, model = make_client(
        ClientKind(args.client),
        role="judge",
        settings=Settings.from_env(),
        live=args.live,
        model=args.model,
    )
    records = judge_items(
        build_items(rewrites, _load_claims(args.claims)),
        rubric,
        client,
        judge_model=model,
        temperature=args.temperature,
        progress=_say,
    )
    write_jsonl(args.out, (r.to_record() for r in records))
    invalid = sum(not r.valid for r in records)
    _say(f"{len(records)} judgements written to {args.out} ({invalid} invalid)")

    # Optionally compare the judge with adjudicated human labels, as two "raters".
    if args.finals:
        finals = [FinalLabel.from_record(r) for r in read_jsonl(args.finals)]
        reference = finals_as_ratings(finals, rubric)
        judge_ratings = [r.to_rating() for r in records if r.valid]
        sys.stdout.write(
            format_agreement_table(agreement_report([*judge_ratings, *reference], rubric))
        )
        sys.stdout.write("\n")
    return 1 if invalid else 0


def cmd_factpico(args: argparse.Namespace) -> int:
    """Download FactPICO, reproduce its metric correlations, or calibrate the judge.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.

    Raises:
        UsageError: If the FactPICO data has not been downloaded yet.
    """
    settings = Settings.from_env()
    directory = data_root(settings) / "factpico"
    csv_path = directory / "all_evaluations.csv"

    # Download: the only step that touches the network.
    if args.action == "download":
        with _fetcher(settings) as fetcher:
            path = factpico.download_factpico(fetcher, directory)
        _say(f"FactPICO evaluations extracted to {path} (CC BY 4.0; never commit it)")
        return 0
    if not csv_path.is_file():
        raise UsageError(f"{csv_path} not found: run `rbbench factpico download` first")
    records = factpico.load_factpico(csv_path)

    # Check: reproduce the published metric correlations (no model involved).
    if args.action == "check":
        sys.stdout.write("| Metric | Kendall tau-b vs Avg. PICO-R | n |\n|---|---|---|\n")
        for metric, (tau, n) in factpico.metric_correlations(records).items():
            value = "undefined" if tau is None else f"{tau:.3f}"
            sys.stdout.write(f"| {metric} | {value} | {n} |\n")
        return 0

    # Calibrate: run the judge on the summaries and correlate with the experts.
    client, model = make_client(
        ClientKind(args.client), role="judge", settings=settings, live=args.live, model=args.model
    )
    result = factpico.calibrate_judge(
        records, load_rubric(), client, judge_model=model, limit=args.limit, progress=_say
    )
    label = " (SYNTHETIC: fake judge)" if result.synthetic else ""
    tau_text = "undefined" if result.tau_b is None else f"{result.tau_b:.3f}"
    sys.stdout.write(
        f"judge {model}{label}: Kendall tau-b {tau_text} over {result.n_summaries} summaries, "
        f"{result.invalid} invalid judgements\n"
    )
    if args.out:
        write_jsonl(args.out, (j.to_record() for j in result.judgements))
    return 0


def cmd_baselines(_args: argparse.Namespace) -> int:
    """Show which optional baseline packages are installed.

    Args:
        _args: Parsed arguments (unused).

    Returns:
        Exit status.
    """
    for name, available in baselines.availability().items():
        sys.stdout.write(f"{name}: {'installed' if available else 'not installed'}\n")
    return 0


def cmd_comprehension(args: argparse.Namespace) -> int:
    """Validate a comprehension question set.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status (1 if invalid).
    """
    errors = comprehension.validate_file(args.file)
    for error in errors:
        _say(error)
    _say("valid" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    """Run the whole pipeline on the fixtures with fake clients and synthetic raters.

    Args:
        args: Parsed arguments.

    Returns:
        Exit status.
    """
    summary = run_dry_run(args.out)
    _say(f"DRY RUN (SYNTHETIC) report: {summary.report_md}")
    return 0


def _add_client_options(parser: argparse.ArgumentParser) -> None:
    """Add the shared LLM client options to a subcommand.

    Args:
        parser: The subcommand parser.
    """
    parser.add_argument("--client", choices=[k.value for k in ClientKind], default="fake")
    parser.add_argument("--live", action="store_true", help="allow paid API calls")
    parser.add_argument("--model", help="model ID override (default: from configuration)")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Returns:
        The parser with one subcommand per step. Defaults inside the data
        directory are :class:`_DataDefault` markers that :func:`main`
        resolves, so building the parser never reads the environment.
    """
    data = _DataDefault
    parser = argparse.ArgumentParser(prog="rbbench", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    # Selection and ingest: the network steps.
    p = sub.add_parser("select", help="build the PROPOSED candidate shortlist (network)")
    p.add_argument("--config", type=Path, default=SELECTION_DIR / "slots_v1.yaml")
    p.add_argument("--out-dir", type=Path, default=SELECTION_DIR)
    p.set_defaults(handler=cmd_select)

    p = sub.add_parser("ingest", help="fetch and parse papers into units and passages")
    source = p.add_mutually_exclusive_group()
    source.add_argument("--candidates", type=Path, default=SELECTION_DIR / "candidates.csv")
    source.add_argument("--fixtures", action="store_true", help="use the committed fixtures")
    p.add_argument("--only", help="comma-separated PMCIDs, paper keys or slot options (S01A)")
    p.add_argument("--min-words", type=int, default=350)
    p.add_argument("--max-words", type=int, default=650)
    p.add_argument("--out", type=Path, default=data("ingest"))
    p.set_defaults(handler=cmd_ingest)

    # Generation steps: rewrite and decompose (fake client unless --live).
    p = sub.add_parser("rewrite", help="rewrite passages for every matrix arm")
    p.add_argument("--ingest", type=Path, default=data("ingest"))
    p.add_argument("--matrix", type=Path, default=CONFIG_DIR / "rewrite_matrix_v1.yaml")
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--out", type=Path, default=data("rewrites.jsonl"))
    _add_client_options(p)
    p.set_defaults(handler=cmd_rewrite)

    p = sub.add_parser("decompose", help="split rewrites into claims")
    p.add_argument("--rewrites", type=Path, default=data("rewrites.jsonl"))
    p.add_argument("--method", choices=[m.value for m in Method], default="llm")
    p.add_argument("--out", type=Path, default=data("claims.jsonl"))
    _add_client_options(p)
    p.set_defaults(handler=cmd_decompose)

    # Human rating: packets, import, agreement, adjudication.
    p = sub.add_parser("packets", help="build per-rater HTML packets and the key")
    p.add_argument("--rewrites", type=Path, default=data("rewrites.jsonl"))
    p.add_argument("--claims", type=Path, default=data("claims.jsonl"))
    p.add_argument("--ingest", type=Path, default=data("ingest"))
    p.add_argument("--raters", required=True, help="comma-separated pseudonymous rater IDs")
    p.add_argument("--packet-id", required=True)
    p.add_argument("--out", type=Path, default=data("packets"))
    p.set_defaults(handler=cmd_packets)

    p = sub.add_parser("import-ratings", help="import rater exports")
    p.add_argument("--key", type=Path, required=True)
    p.add_argument("exports", type=Path, nargs="+")
    p.add_argument("--allow-incomplete", action="store_true")
    p.add_argument("--out", type=Path, default=data("ratings.jsonl"))
    p.set_defaults(handler=cmd_import)

    p = sub.add_parser("agreement", help="per-code inter-rater agreement")
    p.add_argument("ratings", type=Path, nargs="+")
    p.add_argument("--out", type=Path)
    p.set_defaults(handler=cmd_agreement)

    p = sub.add_parser("adjudicate", help="merge ratings into final labels")
    p.add_argument("ratings", type=Path, nargs="+")
    p.add_argument("--adjudications", type=Path)
    p.add_argument("--policy", choices=[x.value for x in Policy], default="unanimous")
    p.add_argument("--out", type=Path, default=data("final_labels.jsonl"))
    p.add_argument("--disagreements", type=Path, default=data("disagreements.csv"))
    p.set_defaults(handler=cmd_adjudicate)

    # The LLM judge and its calibration.
    p = sub.add_parser("judge", help="run the LLM judge on claims and paragraphs")
    p.add_argument("--rewrites", type=Path, default=data("rewrites.jsonl"))
    p.add_argument("--claims", type=Path, default=data("claims.jsonl"))
    p.add_argument("--ingest", type=Path, default=data("ingest"))
    p.add_argument("--temperature", type=float)
    p.add_argument("--finals", type=Path, help="final labels to compare the judge with")
    p.add_argument("--out", type=Path, default=data("judgements.jsonl"))
    _add_client_options(p)
    p.set_defaults(handler=cmd_judge)

    p = sub.add_parser("factpico", help="FactPICO calibration data and judge calibration")
    p.add_argument("action", choices=["download", "check", "calibrate"])
    p.add_argument("--limit", type=int)
    p.add_argument("--out", type=Path)
    _add_client_options(p)
    p.set_defaults(handler=cmd_factpico)

    # Utilities.
    p = sub.add_parser("baselines", help="show which optional baselines are installed")
    p.set_defaults(handler=cmd_baselines)

    p = sub.add_parser("comprehension", help="validate a comprehension question set")
    p.add_argument("action", choices=["validate"])
    p.add_argument("file", type=Path)
    p.set_defaults(handler=cmd_comprehension)

    p = sub.add_parser("dry-run", help="end-to-end run on fixtures; everything synthetic")
    p.add_argument("--out", type=Path, default=data("dry-run"))
    p.set_defaults(handler=cmd_dry_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    Args:
        argv: Arguments (defaults to ``sys.argv[1:]``).

    Returns:
        The exit status.
    """
    args = build_parser().parse_args(argv)
    handler: Handler = args.handler
    try:
        _resolve_data_defaults(args)
        return handler(args)
    except (
        AttributionError,
        ConfigError,
        LicenceGateError,
        LiveCallsNotAllowedError,
        PacketError,
        UsageError,
    ) as exc:
        _say(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
