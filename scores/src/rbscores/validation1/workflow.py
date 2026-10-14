"""The three validation 1 steps behind the CLI: download, calibrate, run.

Everything downloaded or derived from the corpora stays under the data
directory (``RB_DATA_DIR``, default ``data/``, gitignored):

* ``cache/http/``: raw API responses (:class:`rbcore.http.PoliteFetcher` cache);
* ``validation1/pairs-<source>-validation.jsonl``: abstract and lay-summary pairs;
* ``validation1/calibration-windows.jsonl``: training-split body windows;
* ``validation1/manifest.json``: dataset revisions, counts and skipped rows;
* ``validation1/per-pair.jsonl``: per-pair metrics from the last run.

Only aggregate results (the summary JSON and markdown tables) are meant to be
committed, under scores/reports/.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any, Final

from rbcore.http import PoliteFetcher
from rbscores.familiarity import WordfreqFamiliarity
from rbscores.nlp import load_pipeline, pipeline_label
from rbscores.readability.composite import ReferenceStats, load_reference
from rbscores.validation1.calibrate import compute_reference, windows_for
from rbscores.validation1.dataset import (
    DATASETS,
    LayPair,
    article_from_row,
    dataset_revision,
    fetch_rows,
    pair_from_row,
    read_pairs,
    write_pairs,
)
from rbscores.validation1.run import PairResult, evaluate_pairs, summarise

PAIRS_SPLIT: Final = "validation"
CALIBRATION_SPLIT: Final = "train"
DEFAULT_CALIBRATION_ROWS: Final = 100


def validation_dir(data_dir: Path) -> Path:
    """Return the directory holding validation 1's local files.

    Args:
        data_dir: The data directory.

    Returns:
        ``<data_dir>/validation1``.
    """
    return data_dir / "validation1"


def pairs_path(data_dir: Path, source: str) -> Path:
    """Return where one corpus's pairs are stored.

    Args:
        data_dir: The data directory.
        source: "elife" or "plos".

    Returns:
        The JSON Lines path.
    """
    return validation_dir(data_dir) / f"pairs-{source}-{PAIRS_SPLIT}.jsonl"


def download(
    data_dir: Path,
    *,
    sources: Sequence[str] = tuple(DATASETS),
    calibration_rows: int = DEFAULT_CALIBRATION_ROWS,
    fetcher: PoliteFetcher | None = None,
    log: Callable[[str], None] = lambda _: None,
) -> dict[str, Any]:
    """Download validation pairs and calibration articles.

    Args:
        data_dir: The data directory.
        sources: Corpora to download.
        calibration_rows: Training-split rows per corpus for calibration.
        fetcher: Fetcher to use (a cached one under ``data_dir`` by default).
        log: Progress messages.

    Returns:
        The manifest that was written.
    """
    own_fetcher = fetcher is None
    active = fetcher or PoliteFetcher(cache_dir=data_dir / "cache" / "http")
    manifest: dict[str, Any] = {
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "licence": (
            "CC BY 4.0 (PLOS and eLife articles; tomasg25/scientific_lay_summarisation card)"
        ),
        "sources": {},
    }
    windows: list[dict[str, str]] = []
    try:
        for source in sources:
            # Validation-split pairs: the abstract and the lay summary.
            pairs: list[LayPair] = []
            skipped: list[int] = []
            for row, fields in fetch_rows(active, source, PAIRS_SPLIT):
                pair = pair_from_row(source, PAIRS_SPLIT, row, fields)
                if pair is None:
                    skipped.append(row)
                else:
                    pairs.append(pair)
            write_pairs(pairs, pairs_path(data_dir, source))
            log(f"{source}: {len(pairs)} pairs, {len(skipped)} rows skipped")

            # Training-split articles: body windows for the reference statistics.
            articles = [
                article_from_row(source, CALIBRATION_SPLIT, row, fields)
                for row, fields in fetch_rows(
                    active, source, CALIBRATION_SPLIT, limit=calibration_rows
                )
            ]
            source_windows = windows_for(articles)
            windows += [{"source": source, "text": w} for w in source_windows]
            log(
                f"{source}: {len(source_windows)} calibration windows from {len(articles)} articles"
            )

            manifest["sources"][source] = {
                "dataset": DATASETS[source],
                "revision": dataset_revision(active, source),
                "pairs_split": PAIRS_SPLIT,
                "pairs": len(pairs),
                "skipped_rows": skipped,
                "calibration_split": CALIBRATION_SPLIT,
                "calibration_articles": len(articles),
                "calibration_windows": len(source_windows),
            }
    finally:
        if own_fetcher:
            active.close()

    # Write the calibration windows and the manifest.
    out = validation_dir(data_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "calibration-windows.jsonl").open("w", encoding="utf-8") as handle:
        for window in windows:
            handle.write(json.dumps(window, ensure_ascii=False) + "\n")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def calibrate(data_dir: Path, output: Path, *, version: str) -> ReferenceStats:
    """Compute reference statistics from the downloaded calibration windows.

    Args:
        data_dir: The data directory.
        output: Where to write the reference JSON.
        version: Version string to record.

    Returns:
        The statistics written.
    """
    # Read the windows written by the download step.
    path = validation_dir(data_dir) / "calibration-windows.jsonl"
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle if line.strip()]

    # Record where the statistics come from, so the JSON documents itself.
    sources = sorted({row["source"] for row in rows})
    description = (
        "PROVISIONAL. Means and sample SDs of the five readability features over "
        f"{len(rows)} windows of research-article body text: the opening ~150 words "
        "(whole sentences) of up to 4 body sections per article, from the first "
        f"{DEFAULT_CALIBRATION_ROWS} training-split articles of each of "
        f"{', '.join(DATASETS[s] for s in sources)} (PLOS and eLife articles, CC BY 4.0). "
        f"spaCy {pipeline_label(load_pipeline())}, "
        f"wordfreq {package_version('wordfreq')}."
    )
    # Compute and write the statistics.
    reference = compute_reference(
        [row["text"] for row in rows],
        nlp=load_pipeline(),
        familiarity=WordfreqFamiliarity(),
        version=version,
        description=description,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(reference.to_json(), indent=2) + "\n", encoding="utf-8")
    return reference


def run(
    data_dir: Path,
    *,
    reference_path: Path | None = None,
    sources: Sequence[str] = tuple(DATASETS),
    limit: int | None = None,
    log: Callable[[str], None] = lambda _: None,
) -> dict[str, Any]:
    """Run validation 1 on the downloaded pairs.

    Args:
        data_dir: The data directory.
        reference_path: Reference statistics (default: the packaged ones).
        sources: Corpora to include.
        limit: Use at most this many pairs per corpus (None for all).
        log: Progress messages.

    Returns:
        The results document (also used for the markdown tables).
    """
    reference = load_reference(reference_path)
    nlp = load_pipeline()
    familiarity = WordfreqFamiliarity()
    manifest_path = validation_dir(data_dir) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    # Measure every pair of every corpus.
    results: list[PairResult] = []
    skipped: dict[str, list[str]] = {}
    for source in sources:
        pairs = read_pairs(pairs_path(data_dir, source))[:limit]
        log(f"{source}: scoring {len(pairs)} pairs")
        source_results, source_skipped = evaluate_pairs(
            pairs, nlp=nlp, familiarity=familiarity, reference=reference
        )
        results += source_results
        skipped[source] = source_skipped

    _write_per_pair(results, validation_dir(data_dir) / "per-pair.jsonl")
    metadata = {
        "reference_version": reference.version,
        "spacy_model": pipeline_label(nlp),
        "wordfreq_version": package_version("wordfreq"),
        "dataset": {s: manifest["sources"][s] for s in sources if s in manifest["sources"]},
        "skipped_pairs": skipped,
        "limit_per_source": limit,
    }
    return summarise(results, metadata=metadata)


def _write_per_pair(results: Sequence[PairResult], path: Path) -> None:
    """Write per-pair metrics under the data directory (local only, not committed).

    Args:
        results: Pair results.
        path: Output file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for result in results:
            record = {
                "id": result.pair.id,
                "source": result.pair.source,
                "title": result.pair.title,
                **{
                    name: {
                        "words": metrics.words,
                        "values": dict(metrics.values),
                        "undefined_terms": metrics.undefined_terms,
                        "defined_terms": metrics.defined_terms,
                    }
                    for name, metrics in _named_texts(result).items()
                },
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _named_texts(result: PairResult) -> dict[str, Any]:
    """Name the four measured texts of a pair.

    Args:
        result: A pair result.

    Returns:
        ``lay``, ``technical``, ``lay_matched`` and ``technical_matched`` metrics.
    """
    return {
        "lay": result.lay,
        "technical": result.technical,
        "lay_matched": result.lay_matched,
        "technical_matched": result.technical_matched,
    }
