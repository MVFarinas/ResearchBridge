"""FactPICO: expert factuality ratings of LLM plain-language summaries, for judge calibration.

Source and licence (checked 2026-10-13, recorded in docs/licence-inventory.md):

* Paper: Joseph et al., "FactPICO: Factuality Evaluation for Plain Language
  Summarization of Medical Evidence", ACL 2024, arXiv:2402.11456. Its
  Appendix B ("Data Release and License") releases the annotations under
  **CC BY 4.0**.
* Code: github.com/lilywchen/FactPICO, **MIT** (LICENSE at commit
  2e16993a000aedb15cb348b7bcd61070d26bab14). No code is copied from it.
* Data: ``FactPICO.zip`` from the Box link in the repository's
  ``data/README.md``. Downloaded into the gitignored data directory and
  **never committed**. The abstracts inside come from the Evidence Inference
  2.0 / PubMed Open Access subset and keep their own article licences.

``all_evaluations.csv`` has one row per summary (345): the source abstract,
the summary, the generating model, expert ratings for Population,
Intervention, Comparator, Outcome and Results (1-4), their average
("Avg. PICO-R") and the scores of automatic metrics. The paper's
instance-level Kendall tau-b compares each metric with "Avg. PICO-R";
:func:`metric_correlations` reproduces those published values.
"""

from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from rbbench.agreement.stats import kendall_tau_b
from rbbench.judge.harness import JudgeItem, JudgeRecord, judge_items
from rbbench.rubric import Rubric, Unit
from rbbench.sentences import split_sentences
from rbcore.http import PoliteFetcher
from rbcore.llm import LLMClient

FACTPICO_REPO = "https://github.com/lilywchen/FactPICO"
FACTPICO_REPO_COMMIT = "2e16993a000aedb15cb348b7bcd61070d26bab14"
FACTPICO_DOWNLOAD_URL = (
    "https://utexas.box.com/index.php?rm=box_download_shared_file"
    "&shared_name=mpe5idxrqrzs1wcakphng7xfi7h4g83j&file_id=f_1447492862089"
)
# SHA-256 of FactPICO.zip as downloaded on 2026-10-13; a different file is refused.
FACTPICO_ZIP_SHA256 = "ec260d7c69db9537f819fbdf728c997520e55de56b9f03b2980b017c91b9d4f4"
EVALUATIONS_MEMBER = "data/all_evaluations.csv"
MAX_MEMBER_BYTES = 20 * 1024 * 1024
EXPERT_TARGET = "Avg. PICO-R"
EXPERT_COLUMNS = ("Population", "Intervention", "Comparator", "Outcome", "Results", EXPERT_TARGET)
METRIC_COLUMNS = (
    "QAFactEval",
    "QuestEval",
    "AlignScore",
    "DAE",
    "GPT-4",
    "Llama-2",
    "Alpaca",
    "Mistral",
)


class FactPicoError(RuntimeError):
    """Raised when the FactPICO download or file is not what is expected."""


@dataclass(frozen=True, slots=True)
class FactPicoRecord:
    """One FactPICO summary with its expert ratings.

    Attributes:
        record_id: First 12 hex characters of SHA-256(abstract, summary).
        abstract: The source RCT abstract.
        summary: The LLM plain-language summary.
        model_type: The model that wrote the summary.
        expert: Expert ratings by column name (missing values omitted).
        metrics: Published automatic-metric scores by column name.
    """

    record_id: str
    abstract: str
    summary: str
    model_type: str
    expert: dict[str, float]
    metrics: dict[str, float]


def download_factpico(
    fetcher: PoliteFetcher, out_dir: Path, *, expected_sha256: str = FACTPICO_ZIP_SHA256
) -> Path:
    """Download FactPICO.zip, verify it, and extract ``all_evaluations.csv``.

    Args:
        fetcher: The polite fetcher (its cache keeps the zip).
        out_dir: Directory for the extracted CSV (inside the data directory).
        expected_sha256: Required SHA-256 of the zip.

    Returns:
        Path of the extracted CSV.

    Raises:
        FactPicoError: If the checksum differs, the member is missing, or it is
            too large.
    """
    data = fetcher.get(FACTPICO_DOWNLOAD_URL)
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256:
        raise FactPicoError(f"FactPICO.zip has SHA-256 {digest}, expected {expected_sha256}")
    return extract_evaluations(data, out_dir)


def extract_evaluations(zip_bytes: bytes, out_dir: Path) -> Path:
    """Extract only ``data/all_evaluations.csv`` from the zip, safely.

    Only the one known member is read (no path from the archive is used to
    build an output path), and its size is bounded.

    Args:
        zip_bytes: The zip archive.
        out_dir: Destination directory.

    Returns:
        Path of the extracted CSV.

    Raises:
        FactPicoError: If the member is missing or too large.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        try:
            info = archive.getinfo(EVALUATIONS_MEMBER)
        except KeyError as exc:
            raise FactPicoError(f"{EVALUATIONS_MEMBER} is not in the archive") from exc
        if info.file_size > MAX_MEMBER_BYTES:
            raise FactPicoError(f"{EVALUATIONS_MEMBER} is unexpectedly large")
        content = archive.read(info)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "all_evaluations.csv"
    path.write_bytes(content)
    return path


def load_factpico(path: Path) -> list[FactPicoRecord]:
    """Load ``all_evaluations.csv``.

    Args:
        path: The extracted CSV.

    Returns:
        One record per row, in file order.

    Raises:
        FactPicoError: If a required column is missing.
    """
    # Abstracts exceed the csv module's default field limit; raise it for this
    # read only and restore it, so the process-wide setting is left unchanged.
    previous_limit = csv.field_size_limit(MAX_MEMBER_BYTES)
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {"Abstract", "generation", "model_type", EXPERT_TARGET}
            missing = required - set(reader.fieldnames or ())
            if missing:
                raise FactPicoError(f"{path}: missing columns {sorted(missing)}")
            # One record per row; the ID hashes the text so it survives reordering.
            records = []
            for row in reader:
                abstract, summary = row["Abstract"], row["generation"]
                digest = hashlib.sha256(f"{abstract}\x00{summary}".encode()).hexdigest()[:12]
                records.append(
                    FactPicoRecord(
                        record_id=digest,
                        abstract=abstract,
                        summary=summary,
                        model_type=row["model_type"],
                        expert=_numbers(row, EXPERT_COLUMNS),
                        metrics=_numbers(row, METRIC_COLUMNS),
                    )
                )
    finally:
        csv.field_size_limit(previous_limit)
    return records


def _numbers(row: dict[str, str], columns: Sequence[str]) -> dict[str, float]:
    """Read numeric columns, skipping blanks and non-numbers.

    Args:
        row: A CSV row.
        columns: Column names to read.

    Returns:
        Column -> value for the columns that hold a number.
    """
    values: dict[str, float] = {}
    for column in columns:
        try:
            values[column] = float(row[column])
        except (KeyError, ValueError):
            continue
    return values


def metric_correlations(
    records: Sequence[FactPicoRecord], target: str = EXPERT_TARGET
) -> dict[str, tuple[float | None, int]]:
    """Kendall tau-b of each published metric against the expert target.

    Args:
        records: FactPICO records.
        target: Expert column to correlate with.

    Returns:
        Metric -> (tau-b, number of summaries with both values).
    """
    result: dict[str, tuple[float | None, int]] = {}
    for metric in METRIC_COLUMNS:
        pairs = [
            (r.metrics[metric], r.expert[target])
            for r in records
            if metric in r.metrics and target in r.expert
        ]
        tau = (
            kendall_tau_b([a for a, _ in pairs], [b for _, b in pairs]) if len(pairs) > 1 else None
        )
        result[metric] = (tau, len(pairs))
    return result


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """The judge's agreement with FactPICO experts.

    Attributes:
        tau_b: Kendall tau-b between judge scores and the expert target, or
            None when undefined.
        n_summaries: Summaries with a judge score.
        scores: Record ID -> judge score (share of judged claims "supported").
        judgements: Every judge record, for audit.
        invalid: Judge calls whose output was rejected.
        synthetic: True when produced with a fake client or synthetic data.
    """

    tau_b: float | None
    n_summaries: int
    scores: dict[str, float]
    judgements: list[JudgeRecord]
    invalid: int
    synthetic: bool


def calibrate_judge(
    records: Sequence[FactPicoRecord],
    rubric: Rubric,
    client: LLMClient,
    *,
    judge_model: str,
    target: str = EXPERT_TARGET,
    limit: int | None = None,
    progress: Callable[[str], None] | None = None,
) -> CalibrationResult:
    """Score each summary with the claim-level judge and correlate with experts.

    Each summary is split into sentences (one claim each); every claim is
    judged against the abstract with the rubric's claim-level codes; the
    summary's score is the share of validly judged claims labelled
    "supported". This is a deliberately simple aggregation, recorded so a
    better one can be compared later; FactPICO's experts rate PICO elements,
    not claims, so the correlation is the comparable figure, not the scale.

    Args:
        records: FactPICO records.
        rubric: The rubric.
        client: The judge's LLM client.
        judge_model: The judge's model ID (recorded).
        target: Expert column to correlate with.
        limit: Use only the first ``limit`` records (cost control).
        progress: Optional progress callback.

    Returns:
        The calibration result.
    """
    chosen = list(records[:limit] if limit is not None else records)
    items: list[JudgeItem] = []
    owner: dict[str, str] = {}
    for record in chosen:
        source = (("abstract", " ".join(record.abstract.split())),)
        for index, sentence in enumerate(split_sentences(" ".join(record.summary.split())), 1):
            unit_id = f"factpico:{record.record_id}#c{index}"
            owner[unit_id] = record.record_id
            items.append(
                JudgeItem(
                    unit=Unit.CLAIM,
                    unit_id=unit_id,
                    source_passage=source,
                    source_paragraph_id="abstract",
                    rewritten_markup=record.summary,
                    claim=sentence,
                    generator_model=record.model_type,
                )
            )
    judgements = judge_items(items, rubric, client, judge_model=judge_model, progress=progress)

    # Aggregate valid claim judgements into one score per summary.
    supported: dict[str, list[bool]] = {}
    for judgement in judgements:
        if judgement.valid:
            supported.setdefault(owner[judgement.unit_id], []).append(
                judgement.labels.get("support") == "supported"
            )
    scores = {rid: sum(flags) / len(flags) for rid, flags in supported.items()}
    paired = [
        (scores[r.record_id], r.expert[target])
        for r in chosen
        if r.record_id in scores and target in r.expert
    ]
    tau = kendall_tau_b([a for a, _ in paired], [b for _, b in paired]) if len(paired) > 1 else None
    return CalibrationResult(
        tau_b=tau,
        n_summaries=len(paired),
        scores=scores,
        judgements=judgements,
        invalid=sum(not j.valid for j in judgements),
        synthetic=any(j.synthetic for j in judgements),
    )
