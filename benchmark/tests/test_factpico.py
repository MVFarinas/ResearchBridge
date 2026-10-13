"""Tests of the FactPICO loader, download and judge calibration.

Most tests use a SYNTHETIC CSV in FactPICO's column layout. One test runs
on the real data when it has been downloaded into data/ (it is never
committed) and checks the published Kendall tau-b values.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from pathlib import Path

import httpx
import pytest

from rbbench.clients import ClientKind, make_client
from rbbench.judge.factpico import (
    EXPERT_TARGET,
    FactPicoError,
    calibrate_judge,
    download_factpico,
    extract_evaluations,
    load_factpico,
    metric_correlations,
)
from rbbench.paths import data_root
from rbbench.rubric import Rubric
from rbcore.config import Settings
from rbcore.http import PoliteFetcher, RateLimiter

COLUMNS = [
    "Abstract",
    "generation",
    "model_type",
    "Population",
    "Intervention",
    "Comparator",
    "Outcome",
    "Results",
    EXPERT_TARGET,
    "AlignScore",
    "GPT-4",
]


def _write_synthetic_csv(path: Path, rows: int = 6) -> Path:
    """Write a SYNTHETIC CSV in FactPICO's layout; AlignScore equals the target."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        for i in range(rows):
            score = 1 + (i % 4)
            writer.writerow(
                {
                    "Abstract": f"Synthetic abstract {i}. Patients were randomly assigned.",
                    "generation": f"Synthetic summary {i}. It has two sentences.",
                    "model_type": "SYNTHETIC",
                    "Population": score,
                    "Intervention": score,
                    "Comparator": score,
                    "Outcome": score,
                    "Results": score,
                    EXPERT_TARGET: score,
                    "AlignScore": score / 4,
                    "GPT-4": "" if i == 0 else 5 - score,
                }
            )
    return path


def test_loader_reads_ratings_and_metrics(tmp_path: Path) -> None:
    """Expert ratings and metric scores are parsed; blanks are skipped."""
    records = load_factpico(_write_synthetic_csv(tmp_path / "synthetic.csv"))
    assert len(records) == 6
    assert records[1].expert[EXPERT_TARGET] == 2.0
    assert "GPT-4" not in records[0].metrics
    assert len({r.record_id for r in records}) == 6


def test_metric_correlations_on_synthetic_data(tmp_path: Path) -> None:
    """A metric equal to the target has tau 1; a reversed one has tau -1."""
    records = load_factpico(_write_synthetic_csv(tmp_path / "synthetic.csv"))
    correlations = metric_correlations(records)
    align_tau, align_n = correlations["AlignScore"]
    assert align_tau == pytest.approx(1.0)
    assert align_n == 6
    tau, n = correlations["GPT-4"]
    assert n == 5
    assert tau == pytest.approx(-1.0)
    assert correlations["DAE"] == (None, 0)


def test_loading_leaves_the_csv_field_limit_unchanged(tmp_path: Path) -> None:
    """The raised field size limit is restored after a load, even a failing one."""
    before = csv.field_size_limit()
    load_factpico(_write_synthetic_csv(tmp_path / "synthetic.csv"))
    assert csv.field_size_limit() == before
    bad = tmp_path / "bad.csv"
    bad.write_text("Abstract\nx\n", encoding="utf-8")
    with pytest.raises(FactPicoError):
        load_factpico(bad)
    assert csv.field_size_limit() == before


def test_missing_columns_are_reported(tmp_path: Path) -> None:
    """A CSV without the expert target is refused."""
    path = tmp_path / "bad.csv"
    path.write_text("Abstract,generation\nx,y\n", encoding="utf-8")
    with pytest.raises(FactPicoError, match="missing columns"):
        load_factpico(path)


def test_calibration_with_fake_judge_is_synthetic(tmp_path: Path, rubric: Rubric) -> None:
    """The fake judge runs end to end; the result is marked synthetic."""
    records = load_factpico(_write_synthetic_csv(tmp_path / "synthetic.csv"))
    client, model = make_client(ClientKind.FAKE, role="judge", settings=Settings())
    result = calibrate_judge(records, rubric, client, judge_model=model, limit=4)
    assert result.synthetic
    assert result.n_summaries == 4
    assert len(result.judgements) == 8
    assert result.invalid == 0
    assert all(0.0 <= s <= 1.0 for s in result.scores.values())
    again = calibrate_judge(records, rubric, client, judge_model=model, limit=4)
    assert again.tau_b == result.tau_b


def _synthetic_zip(member: str = "data/all_evaluations.csv") -> bytes:
    """A SYNTHETIC zip with one CSV member."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, "Abstract,generation,model_type,Avg. PICO-R\n")
        archive.writestr("../escape.txt", "never extracted")
    return buffer.getvalue()


def test_download_verifies_checksum_and_extracts_one_member(tmp_path: Path) -> None:
    """The zip must match its SHA-256; only the known member is written."""
    payload = _synthetic_zip()

    def handler(request: httpx.Request) -> httpx.Response:
        """Redirect like Box does, then serve the synthetic zip."""
        if request.url.host == "utexas.box.com":
            return httpx.Response(302, headers={"location": "https://public.boxcloud.com/d/1"})
        return httpx.Response(200, content=payload)

    fetcher = PoliteFetcher(
        cache_dir=tmp_path / "cache",
        transport=httpx.MockTransport(handler),
        rate_limiter=RateLimiter(sleep=lambda _s: None),
    )
    with pytest.raises(FactPicoError, match="SHA-256"):
        download_factpico(fetcher, tmp_path / "out")
    good = hashlib.sha256(payload).hexdigest()
    path = download_factpico(fetcher, tmp_path / "out", expected_sha256=good)
    assert path == tmp_path / "out" / "all_evaluations.csv"
    assert sorted(p.name for p in (tmp_path / "out").iterdir()) == ["all_evaluations.csv"]
    assert not (tmp_path / "escape.txt").exists()
    with pytest.raises(FactPicoError, match="not in the archive"):
        extract_evaluations(_synthetic_zip("other.csv"), tmp_path / "x")


REAL_CSV = data_root() / "factpico" / "all_evaluations.csv"


@pytest.mark.factpico
@pytest.mark.skipif(not REAL_CSV.is_file(), reason="FactPICO data not downloaded")
def test_real_factpico_reproduces_published_kendall_tau() -> None:
    """Instance-level tau-b against Avg. PICO-R matches FactPICO's published table.

    Source: Joseph et al. (ACL 2024), FactPICO, instance-level Kendall tau-b
    with expert factuality averaged over PICO and evidence inference:
    QAFactEval 0.289, QuestEval 0.290, AlignScore 0.244, DAE 0.152,
    GPT-4 0.475 (as summarised in research_notes/.../lay_summarisation_faithfulness.md).
    """
    correlations = metric_correlations(load_factpico(REAL_CSV))
    expected = {
        "QAFactEval": 0.289,
        "QuestEval": 0.290,
        "AlignScore": 0.244,
        "DAE": 0.152,
        "GPT-4": 0.475,
    }
    for metric, value in expected.items():
        tau, n = correlations[metric]
        assert n == 345
        assert tau == pytest.approx(value, abs=5e-4), metric
