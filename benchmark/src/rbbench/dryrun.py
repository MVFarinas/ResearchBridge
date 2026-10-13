"""The end-to-end DRY RUN on committed fixtures, with SYNTHETIC outputs throughout.

One call runs every benchmark step on the real CC BY fixtures committed in
Phase 0, using the fake LLM client and synthetic raters:

ingest -> rewrite (fake) -> decompose (fake) -> rater packets -> synthetic
ratings -> import -> agreement -> adjudication (synthetic adjudicator) ->
judge (fake) -> judge-vs-adjudicated agreement -> report.

It proves the pipeline runs and the files fit together. It measures nothing:
every rewrite, claim, rating and judgement in it is synthetic, and the report
says so at the top and in every section.
"""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rbbench.agreement import (
    Basis,
    CodeAgreement,
    FinalLabel,
    agreement_report,
    finals_as_ratings,
    format_agreement_table,
    merge_labels,
    read_adjudications,
    write_disagreements,
)
from rbbench.attribution import attribution_line
from rbbench.claims import Claim, Method, decompose
from rbbench.clients import ClientKind, make_client
from rbbench.ingest import IngestedPaper, ingest_paper, load_passages, load_units, write_ingest
from rbbench.jsonl import read_json, utc_now_iso, write_json, write_jsonl, write_text_atomic
from rbbench.judge.harness import build_items, judge_items
from rbbench.packets.build import build_packets
from rbbench.packets.importer import import_ratings, load_key
from rbbench.paths import CONFIG_DIR, RBCORE_FIXTURES_DIR
from rbbench.ratings import Rating, save_ratings
from rbbench.rewrite.harness import RewriteRecord, load_matrix, run_rewrites
from rbbench.rubric import Rubric, load_rubric
from rbbench.sources.papers import fixture_sources
from rbbench.synthetic import synthetic_export
from rbcore.config import Settings

BANNER = "DRY RUN — SYNTHETIC DATA — NOT RESULTS"
SYNTHETIC_RATERS = (
    ("synthetic-rater-1", 0.0),
    ("synthetic-rater-2", 0.10),
    ("synthetic-rater-3", 0.20),
)
SYNTHETIC_ADJUDICATOR = "synthetic-adjudicator"


@dataclass(frozen=True, slots=True)
class DryRunSummary:
    """What the dry run produced.

    Attributes:
        out_dir: Where everything was written.
        report_md: The Markdown report.
        report_json: The JSON report.
        counts: Headline counts (papers, rewrites, claims, ratings, ...).
    """

    out_dir: Path
    report_md: Path
    report_json: Path
    counts: dict[str, int]


def run_dry_run(out_dir: Path, *, fixtures_dir: Path = RBCORE_FIXTURES_DIR) -> DryRunSummary:
    """Run every step on the fixtures with fake clients and synthetic raters.

    Args:
        out_dir: Output directory (inside the gitignored data directory).
        fixtures_dir: Directory of the committed JATS fixtures.

    Returns:
        The summary, with paths to the report.
    """
    rubric = load_rubric()
    settings = Settings()

    # 1. Ingest the real fixtures (licence gate included).
    papers = [ingest_paper(source) for source in fixture_sources(fixtures_dir)]
    write_ingest(out_dir / "ingest", papers)
    units, passages = load_units(out_dir / "ingest"), load_passages(out_dir / "ingest")
    titles = {paper.paper_key: paper.title for paper in papers}

    # 2. Rewrite every passage in every matrix arm with the fake client.
    generator, requested = make_client(ClientKind.FAKE, role="generation", settings=settings)
    matrix = load_matrix(CONFIG_DIR / "rewrite_matrix_v1.yaml")
    usable = {paper.paper_key for paper in papers if paper.usable}
    rewrites = run_rewrites(
        passages,
        units,
        titles,
        matrix,
        generator,
        requested_model=requested,
        usable_papers=usable,
    )
    write_jsonl(out_dir / "rewrites.jsonl", (r.to_record() for r in rewrites))
    valid = [r for r in rewrites if r.valid]

    # 3. Decompose with the LLM path (fake client), exercising the JSON parser.
    claims = [c for r in valid for c in decompose(r, Method.LLM, client=generator)]
    write_jsonl(out_dir / "claims.jsonl", (c.to_record() for c in claims))

    # 4-5. Packets for synthetic raters, their synthetic exports, and import.
    ratings = _rate_synthetically(valid, claims, rubric, papers, out_dir / "packets")
    save_ratings(out_dir / "ratings.jsonl", ratings)

    # 6-7. Agreement and adjudication by a synthetic adjudicator.
    agreement = agreement_report(ratings, rubric)
    finals = _adjudicate_synthetically(ratings, rubric, out_dir)

    # 8. Judge every claim and paragraph with the fake judge; compare with finals.
    judge_client, judge_model = make_client(ClientKind.FAKE, role="judge", settings=settings)
    judgements = judge_items(
        build_items(valid, claims), rubric, judge_client, judge_model=judge_model
    )
    write_jsonl(out_dir / "judgements.jsonl", (j.to_record() for j in judgements))
    judge_ratings = [j.to_rating() for j in judgements if j.valid]
    judge_vs_final = agreement_report([*judge_ratings, *finals_as_ratings(finals, rubric)], rubric)

    # 9. The report, marked synthetic everywhere.
    counts = {
        "papers": len(papers),
        "usable_papers": sum(p.usable for p in papers),
        "passages": len(passages),
        "rewrites": len(rewrites),
        "valid_rewrites": len(valid),
        "claims": len(claims),
        "claims_from_additions": sum(c.in_addition for c in claims),
        "ratings": len(ratings),
        "final_labels": len(finals),
        "unanimous": sum(f.basis is Basis.UNANIMOUS for f in finals),
        "adjudicated": sum(f.basis is Basis.ADJUDICATED for f in finals),
        "judgements": len(judgements),
        "valid_judgements": len(judge_ratings),
    }
    report = {
        "title": BANNER,
        "dry_run": True,
        "synthetic": True,
        "generated": utc_now_iso(),
        "rubric": {"id": rubric.id, "sha256": rubric.sha256, "status": rubric.status},
        "counts": counts,
        "papers": [_paper_summary(p) for p in papers],
        "rater_agreement": [e.to_record() for e in agreement],
        "judge_vs_adjudicated": [e.to_record() for e in judge_vs_final],
    }
    write_json(out_dir / "report.json", report)
    markdown = _markdown(report, papers, rewrites, agreement, judge_vs_final)
    write_text_atomic(out_dir / "report.md", markdown)
    return DryRunSummary(out_dir, out_dir / "report.md", out_dir / "report.json", counts)


def _rate_synthetically(
    rewrites: list[RewriteRecord],
    claims: list[Claim],
    rubric: Rubric,
    papers: list[IngestedPaper],
    packet_dir: Path,
) -> list[Rating]:
    """Build packets, write one synthetic export per rater, and import them.

    Args:
        rewrites: Valid rewrites.
        claims: Their claims.
        rubric: The rubric.
        papers: Ingested papers (titles and attribution).
        packet_dir: Where packets and exports go.

    Returns:
        The imported (synthetic) ratings from every rater.
    """
    # The same attribution the CLI uses: the source text shown is real CC BY text.
    attributions = {p.paper_key: attribution_line(p.to_record()) for p in papers if p.usable}
    build_packets(
        rewrites,
        claims,
        rubric,
        [rater for rater, _ in SYNTHETIC_RATERS],
        packet_dir,
        packet_id="dry-run",
        titles={p.paper_key: p.title for p in papers},
        attributions=attributions,
    )
    key = load_key(packet_dir / "key.json")
    ratings: list[Rating] = []
    for rater, change_rate in SYNTHETIC_RATERS:
        packet = read_json(packet_dir / f"{rater}.packet.json")
        export = synthetic_export(
            packet, base_seed="dry-run", rater_seed=rater, change_rate=change_rate
        )
        path = packet_dir / f"{rater}.ratings.json"
        write_json(path, export)
        # Through the real importer, so the dry run exercises its validation.
        ratings.extend(import_ratings(path, key, rubric))
    return ratings


def _adjudicate_synthetically(
    ratings: list[Rating], rubric: Rubric, out_dir: Path
) -> list[FinalLabel]:
    """Merge ratings, let a synthetic adjudicator resolve disagreements, merge again.

    The synthetic adjudicator takes synthetic-rater-1's value, so the step
    exercises the CSV round trip without pretending to judge anything.

    Args:
        ratings: All synthetic ratings.
        rubric: The rubric.
        out_dir: Where the disagreement CSVs and final labels go.

    Returns:
        The final labels after adjudication.
    """
    first = merge_labels(ratings, rubric)
    disagreements = out_dir / "disagreements.csv"
    write_disagreements(disagreements, first, rubric)
    first_rater = SYNTHETIC_RATERS[0][0]

    # Fill the adjudication columns as the synthetic adjudicator.
    with disagreements.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        values = dict(part.split("=", 1) for part in row["rater_values"].split("; "))
        row["adjudicated_value"] = values[first_rater]
        row["adjudicator"] = SYNTHETIC_ADJUDICATOR
        row["note"] = "SYNTHETIC: took synthetic-rater-1's value"
    adjudicated = out_dir / "adjudicated.csv"
    with adjudicated.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["unit"])
        writer.writeheader()
        writer.writerows(rows)

    finals = merge_labels(ratings, rubric, adjudications=read_adjudications(adjudicated))
    write_jsonl(out_dir / "final_labels.jsonl", (f.to_record() for f in finals))
    return finals


def _paper_summary(paper: IngestedPaper) -> dict[str, Any]:
    """Summarise one ingested paper for the report.

    Args:
        paper: The paper.

    Returns:
        Key, title, licence, usability, units and passage.
    """
    return {
        "paper_key": paper.paper_key,
        "title": paper.title,
        "licence": paper.licence,
        "usable": paper.usable,
        "units": len(paper.units),
        "passage": paper.passage.passage_id if paper.passage else None,
        "reasons": list(paper.licence_reasons),
    }


def _markdown(
    report: dict[str, Any],
    papers: list[IngestedPaper],
    rewrites: list[RewriteRecord],
    agreement: list[CodeAgreement],
    judge_vs_final: list[CodeAgreement],
) -> str:
    """Render the dry-run report as Markdown.

    Args:
        report: The JSON report.
        papers: Ingested papers.
        rewrites: All rewrite records.
        agreement: Rater agreement entries.
        judge_vs_final: Judge-vs-adjudicated agreement entries.

    Returns:
        The Markdown text.
    """
    # Pre-render the pieces that need loops; the template below is plain text.
    counts = report["counts"]
    arms = Counter(r.arm for r in rewrites if r.valid)
    paper_rows = "\n".join(
        f"| {p.paper_key} | {p.licence} | {'yes' if p.usable else 'no'} | {len(p.units)} "
        f"| {p.passage.passage_id if p.passage else '—'} |"
        for p in papers
    )
    return f"""# {BANNER}

> Everything below was produced by the **dry run**: real CC BY fixtures from
> `libs/rbcore/tests/fixtures/jats/` were ingested, then rewritten by a **fake** LLM client,
> decomposed by a fake client, rated by **synthetic** raters, adjudicated by a **synthetic**
> adjudicator and judged by a **fake** judge. No number here says anything about any model,
> rewrite or rater. It only shows that the pipeline runs end to end.

Generated {report["generated"]} with rubric `{report["rubric"]["id"]}`
({report["rubric"]["status"]}).

## Ingest (real fixtures; licence decisions are real)

| Paper | Licence | Usable | Units | Proposed passage |
|---|---|---|---|---|
{paper_rows}

## Rewrites (SYNTHETIC: fake client)

{counts["rewrites"]} rewrites, {counts["valid_rewrites"]} valid; per arm: {dict(arms)}.

## Claims (SYNTHETIC: fake decomposition)

{counts["claims"]} claims, {counts["claims_from_additions"]} from marked additions.

## Rater agreement (SYNTHETIC raters: not a result)

{counts["ratings"]} synthetic ratings from {len(SYNTHETIC_RATERS)} synthetic raters.

{format_agreement_table(agreement)}

## Adjudication (SYNTHETIC adjudicator)

{counts["final_labels"]} final labels: {counts["unanimous"]} unanimous, {counts["adjudicated"]}
adjudicated (synthetic adjudicator took synthetic-rater-1's value).

## Judge vs adjudicated labels (SYNTHETIC judge and labels: not a result)

{counts["valid_judgements"]} of {counts["judgements"]} fake judgements were valid.

{format_agreement_table(judge_vs_final)}

---

{BANNER}
"""
