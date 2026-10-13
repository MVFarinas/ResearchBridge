"""JSON Lines and JSON file helpers with atomic writes.

Every benchmark step reads and writes JSON Lines so a run can be inspected
with ordinary tools and resumed step by step. Writes go through a temporary
file and an atomic rename, so an interrupted step never leaves a truncated
file that a later step would trust.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterable, Iterator, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string with seconds precision.

    Returns:
        For example ``2026-10-13T04:05:06Z``.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_text_atomic(path: Path, text: str) -> None:
    """Write a text file through a temporary file and an atomic rename.

    Args:
        path: Destination; parent directories are created.
        text: UTF-8 content.

    Raises:
        OSError: If the file cannot be written; the temporary file is removed.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        temporary.replace(path)
    except BaseException:
        # Never leave a half-written temporary file behind.
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def write_jsonl(path: Path, records: Iterable[Mapping[str, Any]]) -> int:
    """Write records as JSON Lines, atomically.

    Args:
        path: Destination file.
        records: JSON-serialisable mappings.

    Returns:
        The number of records written.
    """
    lines = [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records]
    write_text_atomic(path, "".join(f"{line}\n" for line in lines))
    return len(lines)


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    """Yield the records of a JSON Lines file, skipping blank lines.

    Args:
        path: The file.

    Yields:
        One dict per non-blank line.

    Raises:
        ValueError: If a line is not a JSON object (the message names the line).
    """
    with path.open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise ValueError(f"{path}:{number}: expected a JSON object")
            yield record


def write_json(path: Path, data: Any) -> None:
    """Write one JSON document, pretty-printed, atomically.

    Args:
        path: Destination file.
        data: JSON-serialisable value.
    """
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    """Read one JSON document.

    Args:
        path: The file.

    Returns:
        The parsed value.
    """
    return json.loads(path.read_text(encoding="utf-8"))
