"""Well-known locations inside the repository and the gitignored data directory.

The benchmark's versioned inputs (prompts, rubric, selection config) live in
``benchmark/`` and are committed; everything downloaded or generated lives
under ``<data dir>/benchmark/`` and is never committed (docs/conventions.md).
The package is installed editable from the monorepo, so these paths are
resolved relative to this source file.
"""

from __future__ import annotations

from pathlib import Path

from rbcore.config import Settings

# src/rbbench/paths.py -> parents: [0]=rbbench, [1]=src, [2]=benchmark, [3]=repo root.
BENCHMARK_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BENCHMARK_ROOT.parent

PROMPTS_DIR = BENCHMARK_ROOT / "prompts"
RUBRIC_DIR = BENCHMARK_ROOT / "rubric"
SELECTION_DIR = BENCHMARK_ROOT / "selection"
CONFIG_DIR = BENCHMARK_ROOT / "config"
COMPREHENSION_DIR = BENCHMARK_ROOT / "comprehension"

# The real CC BY JATS fixtures committed in Phase 0 (attribution in their README).
RBCORE_FIXTURES_DIR = REPO_ROOT / "libs" / "rbcore" / "tests" / "fixtures" / "jats"


def data_root(settings: Settings | None = None) -> Path:
    """Return the benchmark's working directory inside the data directory.

    Args:
        settings: Runtime settings; read from the environment when None.

    Returns:
        ``<RB_DATA_DIR>/benchmark``. A relative ``RB_DATA_DIR`` is resolved
        against the repository root, so commands work from any directory.
    """
    settings = settings or Settings.from_env()
    base = settings.data_dir if settings.data_dir.is_absolute() else REPO_ROOT / settings.data_dir
    return base / "benchmark"
