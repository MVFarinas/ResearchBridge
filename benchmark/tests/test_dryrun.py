"""The end-to-end dry run on the committed fixtures (everything SYNTHETIC)."""

from __future__ import annotations

import json
from pathlib import Path

from rbbench.dryrun import BANNER, run_dry_run
from rbbench.jsonl import read_jsonl


def test_dry_run_produces_a_synthetic_report(tmp_path: Path) -> None:
    """Every step runs; every output is marked synthetic and the report says DRY RUN."""
    summary = run_dry_run(tmp_path)
    counts = summary.counts
    assert counts["papers"] == 4
    assert counts["usable_papers"] == 3
    assert counts["rewrites"] == 6
    assert counts["valid_rewrites"] == 6
    assert counts["claims"] > 0
    assert counts["ratings"] == 3 * (counts["claims"] + 6 * 3)
    assert counts["unanimous"] + counts["adjudicated"] == counts["final_labels"]
    assert counts["valid_judgements"] == counts["judgements"]

    markdown = summary.report_md.read_text(encoding="utf-8")
    assert markdown.startswith(f"# {BANNER}")
    assert markdown.rstrip().endswith(BANNER)
    assert markdown.count("SYNTHETIC") >= 5
    report = json.loads(summary.report_json.read_text(encoding="utf-8"))
    assert report["dry_run"] is True
    assert report["synthetic"] is True

    # Every generated record carries the synthetic flag.
    for name in ("rewrites.jsonl", "claims.jsonl", "ratings.jsonl", "judgements.jsonl"):
        records = list(read_jsonl(tmp_path / name))
        assert records, name
        assert all(record["synthetic"] for record in records), name
    assert (tmp_path / "packets" / "synthetic-rater-1.html").is_file()
    assert (tmp_path / "packets" / "key.json").is_file()


def test_dry_run_is_deterministic(tmp_path: Path) -> None:
    """Two runs give identical synthetic ratings and final labels."""
    run_dry_run(tmp_path / "a")
    run_dry_run(tmp_path / "b")
    for name in ("ratings.jsonl", "final_labels.jsonl", "claims.jsonl"):
        first = (tmp_path / "a" / name).read_text(encoding="utf-8")
        assert first == (tmp_path / "b" / name).read_text(encoding="utf-8"), name
