"""Tests of the rbbench command line, step by step on the fixtures (SYNTHETIC outputs)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from rbbench.cli import main
from rbbench.jsonl import read_json, read_jsonl, write_json, write_jsonl
from rbbench.paths import COMPREHENSION_DIR, SELECTION_DIR
from rbbench.synthetic import synthetic_export


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point RB_DATA_DIR at a temporary directory and clear any API settings."""
    monkeypatch.setenv("RB_DATA_DIR", str(tmp_path / "data"))
    for name in ("ANTHROPIC_API_KEY", "RB_LLM_GENERATION_MODEL", "RB_LLM_JUDGE_MODEL"):
        monkeypatch.delenv(name, raising=False)


def test_step_by_step_pipeline(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Ingest -> rewrite -> decompose -> packets -> import -> agreement -> adjudicate -> judge."""
    work = tmp_path / "work"
    assert main(["ingest", "--fixtures", "--out", str(work / "ingest")]) == 0
    assert len(list(read_jsonl(work / "ingest" / "passages.jsonl"))) == 3

    assert main(["rewrite", "--ingest", str(work / "ingest"), "--out", str(work / "rw.jsonl")]) == 0
    assert (
        main(
            ["decompose", "--rewrites", str(work / "rw.jsonl"), "--out", str(work / "claims.jsonl")]
        )
        == 0
    )
    assert (
        main(
            [
                "decompose",
                "--rewrites",
                str(work / "rw.jsonl"),
                "--method",
                "sentences",
                "--out",
                str(work / "claims-sentences.jsonl"),
            ]
        )
        == 0
    )
    llm_claims = [r["text"] for r in read_jsonl(work / "claims.jsonl")]
    sentence_claims = [r["text"] for r in read_jsonl(work / "claims-sentences.jsonl")]
    assert llm_claims == sentence_claims

    packets = work / "packets"
    assert (
        main(
            [
                "packets",
                "--rewrites",
                str(work / "rw.jsonl"),
                "--claims",
                str(work / "claims.jsonl"),
                "--ingest",
                str(work / "ingest"),
                "--raters",
                "synthetic-a,synthetic-b",
                "--packet-id",
                "cli-test",
                "--out",
                str(packets),
            ]
        )
        == 0
    )
    # Every item shows its paper's attribution: title, DOI, licence and the NLM credit.
    packet = read_json(packets / "synthetic-a.packet.json")
    attributions = {item["attribution"] for item in packet["items"]}
    assert attributions
    for line in attributions:
        assert "https://doi.org/10.7554/eLife." in line
        assert "Licence: CC BY" in line
        assert "U.S. National Library of Medicine" in line

    # Two synthetic raters fill in their packets.
    exports = []
    for rater, rate in (("synthetic-a", 0.0), ("synthetic-b", 0.2)):
        export = synthetic_export(
            read_json(packets / f"{rater}.packet.json"),
            base_seed="cli",
            rater_seed=rater,
            change_rate=rate,
        )
        path = work / f"{rater}.ratings.json"
        write_json(path, export)
        exports.append(str(path))
    ratings = work / "ratings.jsonl"
    assert (
        main(
            ["import-ratings", "--key", str(packets / "key.json"), *exports, "--out", str(ratings)]
        )
        == 0
    )

    capsys.readouterr()
    assert main(["agreement", str(ratings), "--out", str(work / "agreement.json")]) == 0
    assert "| `support` | claim |" in capsys.readouterr().out

    finals, disagreements = work / "finals.jsonl", work / "disagreements.csv"
    status = main(
        ["adjudicate", str(ratings), "--out", str(finals), "--disagreements", str(disagreements)]
    )
    with disagreements.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert status == (1 if rows else 0)
    # A synthetic adjudicator resolves every disagreement; then nothing is unresolved.
    for row in rows:
        row["adjudicated_value"] = row["allowed_values"].split("|")[0]
        row["adjudicator"] = "synthetic-adjudicator"
    with disagreements.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["unit"])
        writer.writeheader()
        writer.writerows(rows)
    assert (
        main(
            [
                "adjudicate",
                str(ratings),
                "--adjudications",
                str(disagreements),
                "--out",
                str(finals),
                "--disagreements",
                str(work / "remaining.csv"),
            ]
        )
        == 0
    )

    capsys.readouterr()
    assert (
        main(
            [
                "judge",
                "--rewrites",
                str(work / "rw.jsonl"),
                "--claims",
                str(work / "claims.jsonl"),
                "--ingest",
                str(work / "ingest"),
                "--finals",
                str(finals),
                "--out",
                str(work / "judgements.jsonl"),
            ]
        )
        == 0
    )
    # Judge-vs-adjudicated agreement is printed, two "raters": the judge and the finals.
    table = capsys.readouterr().out
    assert "| `dropped_limitation` | paragraph | 18 | 2 |" in table
    assert all(r["synthetic"] for r in read_jsonl(work / "judgements.jsonl"))


def test_real_client_without_live_or_key_is_refused(tmp_path: Path) -> None:
    """--client anthropic needs --live, and --live needs a key: exit status 2."""
    assert main(["ingest", "--fixtures", "--out", str(tmp_path / "ingest")]) == 0
    base = [
        "rewrite",
        "--ingest",
        str(tmp_path / "ingest"),
        "--client",
        "anthropic",
        "--out",
        str(tmp_path / "rw.jsonl"),
    ]
    assert main(base) == 2
    assert main([*base, "--live", "--model", "model-from-config"]) == 2
    assert not (tmp_path / "rw.jsonl").exists()


def test_dry_run_comprehension_and_baselines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The utility commands run and report what they should."""
    assert main(["dry-run", "--out", str(tmp_path / "dry")]) == 0
    assert (tmp_path / "dry" / "report.md").read_text(encoding="utf-8").startswith("# DRY RUN")
    assert main(["comprehension", "validate", str(COMPREHENSION_DIR / "template_v1.yaml")]) == 0
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"status": "FINAL"}), encoding="utf-8")
    assert main(["comprehension", "validate", str(bad)]) == 1
    capsys.readouterr()
    assert main(["baselines"]) == 0
    assert "alignscore: not installed" in capsys.readouterr().out


def test_factpico_check_and_fake_calibration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Factpico check and calibrate run on a SYNTHETIC CSV in the data directory."""
    directory = tmp_path / "data" / "benchmark" / "factpico"
    directory.mkdir(parents=True)
    with (directory / "all_evaluations.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Abstract", "generation", "model_type", "Avg. PICO-R", "AlignScore"])
        for i in range(4):
            writer.writerow(
                [
                    f"Synthetic abstract {i}.",
                    f"Synthetic summary {i}.",
                    "SYNTHETIC",
                    i + 1,
                    (i + 1) / 4,
                ]
            )
    capsys.readouterr()
    assert main(["factpico", "check"]) == 0
    assert "| AlignScore | 1.000 | 4 |" in capsys.readouterr().out
    assert main(["factpico", "calibrate", "--limit", "3"]) == 0
    assert "SYNTHETIC: fake judge" in capsys.readouterr().out


def _ingest_fixtures(directory: Path) -> None:
    """Ingest the committed fixtures into a directory."""
    assert main(["ingest", "--fixtures", "--out", str(directory)]) == 0


def test_rewrite_refuses_an_edited_passage_over_refused_text(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A passage the owner points at gate-refused paragraphs stops the run; nothing is written."""
    ingest = tmp_path / "ingest"
    _ingest_fixtures(ingest)
    # The Europe PMC copy has no machine-readable licence, so its units are not rewritable.
    refused = [
        u for u in read_jsonl(ingest / "units.jsonl") if u["paper_key"] == "elife-93719-europepmc"
    ]
    assert refused
    assert not any(u["can_rewrite"] for u in refused)
    passages = list(read_jsonl(ingest / "passages.jsonl"))
    passages.append(
        {
            "record_type": "passage",
            "passage_id": "elife-93719-europepmc:edited",
            "paper_key": "elife-93719-europepmc",
            "paragraph_ids": [refused[0]["paragraph_id"], refused[1]["paragraph_id"]],
            "words": refused[0]["words"] + refused[1]["words"],
            "strategy": "edited",
            "status": "PROPOSED",
        }
    )
    write_jsonl(ingest / "passages.jsonl", passages)

    out = tmp_path / "rw.jsonl"
    capsys.readouterr()
    assert main(["rewrite", "--ingest", str(ingest), "--out", str(out)]) == 2
    error = capsys.readouterr().err
    assert "licence gate" in error
    assert f"elife-93719-europepmc#{refused[0]['paragraph_id']} may not be rewritten" in error
    assert not out.exists()


def test_packets_and_judge_refuse_rewrites_of_refused_papers(tmp_path: Path) -> None:
    """Rewrites whose paper the ingest gate refused never reach packets or the judge."""
    ingest = tmp_path / "ingest"
    _ingest_fixtures(ingest)
    assert main(["rewrite", "--ingest", str(ingest), "--out", str(tmp_path / "rw.jsonl")]) == 0
    claims = tmp_path / "claims.jsonl"
    assert main(["decompose", "--rewrites", str(tmp_path / "rw.jsonl"), "--out", str(claims)]) == 0

    # Mark one paper unusable after the fact, as a later refusal would.
    papers = list(read_jsonl(ingest / "papers.jsonl"))
    for paper in papers:
        if paper["paper_key"] == "elife-65180-pmc-s3":
            paper["usable"] = False
    write_jsonl(ingest / "papers.jsonl", papers)

    common = ["--rewrites", str(tmp_path / "rw.jsonl"), "--claims", str(claims)]
    common += ["--ingest", str(ingest)]
    packets = tmp_path / "packets"
    packet_args = ["--raters", "synthetic-a", "--packet-id", "x", "--out", str(packets)]
    assert main(["packets", *common, *packet_args]) == 2
    assert not packets.exists()
    judgements = tmp_path / "judgements.jsonl"
    assert main(["judge", *common, "--out", str(judgements)]) == 2
    assert not judgements.exists()


def test_packets_refuse_a_rater_id_that_escapes_the_output_directory(tmp_path: Path) -> None:
    """--raters ../x is refused with exit status 2 and nothing is written outside --out."""
    ingest = tmp_path / "ingest"
    _ingest_fixtures(ingest)
    assert main(["rewrite", "--ingest", str(ingest), "--out", str(tmp_path / "rw.jsonl")]) == 0
    claims = tmp_path / "claims.jsonl"
    assert main(["decompose", "--rewrites", str(tmp_path / "rw.jsonl"), "--out", str(claims)]) == 0
    args = ["packets", "--rewrites", str(tmp_path / "rw.jsonl"), "--claims", str(claims)]
    args += ["--ingest", str(ingest), "--raters", "../escaped-rater", "--packet-id", "x"]
    assert main([*args, "--out", str(tmp_path / "packets")]) == 2
    assert not (tmp_path / "escaped-rater.html").exists()
    assert not (tmp_path / "packets").exists()


def test_ingest_only_must_match_and_cannot_combine_with_fixtures(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--only that matches nothing, or --only with --fixtures, exits 2 and writes nothing."""
    out = tmp_path / "ingest"
    capsys.readouterr()
    assert main(["ingest", "--fixtures", "--only", "S01A", "--out", str(out)]) == 2
    assert "cannot be used with --fixtures" in capsys.readouterr().err
    candidates = str(SELECTION_DIR / "candidates.csv")
    for only in ("NOT-A-CANDIDATE", "S01A,S99Z", ","):
        assert main(["ingest", "--candidates", candidates, "--only", only, "--out", str(out)]) == 2
        assert "--only matches no candidate" in capsys.readouterr().err
    assert not out.exists()


def test_factpico_without_downloaded_data_gives_a_hint(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Before the download, check and calibrate exit 2 and say to run the download."""
    for action in ("check", "calibrate"):
        capsys.readouterr()
        assert main(["factpico", action]) == 2
        assert "run `rbbench factpico download` first" in capsys.readouterr().err


def test_bad_settings_do_not_break_help_and_are_reported_cleanly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An invalid RB_DB_PORT leaves --help working and makes a command exit 2, no traceback."""
    monkeypatch.setenv("RB_DB_PORT", "not-a-port")
    with pytest.raises(SystemExit) as exited:
        main(["--help"])
    assert exited.value.code == 0
    capsys.readouterr()
    assert main(["dry-run"]) == 2
    assert "RB_DB_PORT must be an integer" in capsys.readouterr().err
