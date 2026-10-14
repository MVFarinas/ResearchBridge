"""Tests for the rbscores command line."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from rbscores import cli
from rbscores.readability.features import FEATURE_NAMES
from rbscores.status import PROVISIONAL_NOTICE
from rbscores.validation1 import workflow
from rbscores.validation1.dataset import LayPair
from rbscores.validation1.run import METRICS, PairResult, TextMetrics, summarise

SYNTHETIC_TEXT = (
    "Body mass index (BMI) was recorded in all patients.\n\n"
    "Nephrons filter the blood. Apoptosis removed damaged hepatocytes."
)


def _run(*args: str) -> tuple[int, str]:
    """Run the CLI and capture its output."""
    out = io.StringIO()
    status = cli.main(list(args), out=out)
    return status, out.getvalue()


@pytest.fixture
def text_file(tmp_path: Path) -> Path:
    """A small SYNTHETIC text file."""
    path = tmp_path / "synthetic.txt"
    path.write_text(SYNTHETIC_TEXT, encoding="utf-8")
    return path


def test_score_text_output(text_file: Path) -> None:
    """The text report starts with the provisional notice and lists every unit."""
    status, output = _run("score", str(text_file))
    assert status == 0
    assert output.startswith(PROVISIONAL_NOTICE)
    assert "PAPER" in output
    assert "\np1 " in output
    assert "\np2 " in output
    assert "Top undefined terms" in output


def test_score_json_for_jats(jats_fixtures: Path) -> None:
    """JSON output for a real JATS article has sections and no paragraphs when asked."""
    status, output = _run(
        "score", str(jats_fixtures / "elife-93719-pmc-s3.xml"), "--json", "--no-paragraphs"
    )
    data = json.loads(output)
    assert status == 0
    assert data["provisional"] is True
    assert data["paragraphs"] is None
    assert data["document"]["identifier"] == "10.7554/eLife.93719"
    assert {s["id"] for s in data["sections"]} >= {"abs1"}
    assert data["paper"]["burden"]["undefined_term_count"] > 0


def test_terms_json(text_file: Path) -> None:
    """Ranked terms come with locations and the notice."""
    status, output = _run("terms", str(text_file), "--json", "--limit", "2")
    data = json.loads(output)
    assert status == 0
    assert data["notice"] == PROVISIONAL_NOTICE
    assert 0 < len(data["terms"]) <= 2
    assert data["terms"][0]["locations"][0]["paragraph_id"] in {"p1", "p2"}


def test_terms_text(text_file: Path) -> None:
    """The text listing names each term's paragraphs."""
    status, output = _run("terms", str(text_file))
    assert status == 0
    assert "[p2]" in output


def test_human_validate_and_evaluate(repo_root: Path) -> None:
    """The documented synthetic examples validate and evaluate."""
    examples = repo_root / "docs" / "data-formats" / "examples"
    status, output = _run(
        "human", "validate", "pairwise", str(examples / "pairwise-judgements.synthetic.json")
    )
    assert status == 0
    assert output.startswith("OK ")
    assert "[SYNTHETIC]" in output

    status, output = _run("human", "evaluate", "marks", str(examples / "term-marks.synthetic.json"))
    data = json.loads(output)
    assert status == 0
    assert data["notice"] == PROVISIONAL_NOTICE
    assert data["synthetic"] is True
    assert data["marks"] == 4


def test_human_validate_reports_invalid_files(tmp_path: Path) -> None:
    """An invalid file exits 1 and lists the problems."""
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"schema": "nope"}), encoding="utf-8")
    status, output = _run("human", "validate", "marks", str(path))
    assert status == 1
    assert output.startswith("INVALID")
    assert "'schema' must be" in output


def test_validation1_steps_call_the_workflow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Download passes its options through; run writes the JSON and markdown files."""
    calls: dict[str, Any] = {}

    def fake_download(data_dir: Path, **kwargs: Any) -> dict[str, Any]:
        """Record the download call."""
        calls["download"] = (data_dir, kwargs["sources"], kwargs["calibration_rows"])
        return {}

    def fake_run(data_dir: Path, **kwargs: Any) -> dict[str, Any]:
        """Return a summary of one SYNTHETIC pair."""
        metrics = TextMetrics(
            words=10,
            values=dict.fromkeys(METRICS, 1.0),
            z_scores=dict.fromkeys(FEATURE_NAMES, 0.0),
            undefined_terms=0,
            defined_terms=0,
        )
        pair = LayPair("s-1", "elife", "validation", 0, "Synthetic", "2020", "a", "b")
        return summarise([PairResult(pair, metrics, metrics, metrics, metrics)], metadata={})

    monkeypatch.setattr(workflow, "download", fake_download)
    monkeypatch.setattr(workflow, "run", fake_run)

    status, _ = _run("validation1", "download", "--data-dir", str(tmp_path), "--sources", "plos")
    assert status == 0
    assert calls["download"] == (tmp_path, ["plos"], workflow.DEFAULT_CALIBRATION_ROWS)

    results, tables = tmp_path / "results.json", tmp_path / "tables.md"
    status, output = _run(
        "validation1",
        "run",
        "--data-dir",
        str(tmp_path),
        "--output",
        str(results),
        "--markdown",
        str(tables),
    )
    assert status == 0
    assert json.loads(results.read_text())["pairs"] == {"elife": 1, "all": 1}
    assert tables.read_text() == output
    assert "**Composite readability**" in output


def test_non_utf8_text_file_is_a_one_line_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A text file that is not UTF-8 exits 1 with a message, not a traceback."""
    path = tmp_path / "latin1.txt"
    path.write_bytes("Café au lait.".encode("latin-1"))
    status, output = _run("score", str(path))
    assert (status, output) == (1, "")
    message = capsys.readouterr().err
    assert message.startswith(f"rbscores: {path} is not UTF-8 text")
    assert message.count("\n") == 1


def test_missing_input_file_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A missing input path exits 1 and names the file."""
    missing = tmp_path / "absent.txt"
    status, _ = _run("terms", str(missing))
    assert status == 1
    assert capsys.readouterr().err == f"rbscores: {missing}: no such file\n"


def test_malformed_jats_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Broken XML exits 1 with the parser's reason."""
    path = tmp_path / "broken.xml"
    path.write_text("<article><body>", encoding="utf-8")
    status, _ = _run("score", str(path))
    assert status == 1
    assert capsys.readouterr().err.startswith(f"rbscores: {path} is not usable JATS XML")


@pytest.mark.parametrize("step", ["run", "calibrate"])
def test_validation1_without_download_says_what_to_do(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], step: str
) -> None:
    """Running or calibrating before downloading points at the download step."""
    extra = (
        ["--output", str(tmp_path / "ref.json"), "--version", "v"] if step == "calibrate" else []
    )
    status, _ = _run("validation1", step, "--data-dir", str(tmp_path / "empty"), *extra)
    assert status == 1
    message = capsys.readouterr().err
    assert str(tmp_path / "empty" / "validation1") in message
    assert message.endswith("not found; run `rbscores validation1 download` first\n")


def test_malformed_reference_file_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reference JSON without the required fields exits 1 with the reason."""
    reference = tmp_path / "reference.json"
    reference.write_text(json.dumps({"version": "x"}), encoding="utf-8")
    status, _ = _run(
        "validation1", "run", "--data-dir", str(tmp_path), "--reference", str(reference)
    )
    assert status == 1
    assert capsys.readouterr().err.startswith("rbscores: malformed reference statistics")
