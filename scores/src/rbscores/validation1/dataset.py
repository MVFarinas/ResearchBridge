"""The PLOS and eLife lay-summarisation corpora: download and preparation.

Source: the corpora of Goldsack et al., "Making Science Simple: Corpora for
the Lay Summarisation of Scientific Literature", EMNLP 2022. Each record is a
full biomedical article (abstract first) paired with its lay summary: an eLife
digest (written by eLife's editors) or a PLOS author summary (written by the
authors).

Licence, checked on 2026-10-13: the authors' Hugging Face card
(``tomasg25/scientific_lay_summarisation``) declares CC BY 4.0, and the texts
are PLOS and eLife articles, which the publishers release under CC BY 4.0
(some PLOS under CC0). The authors' GitHub repository
(``TGoldsack1/Corpora_for_Lay_Summarisation``) has no licence file. The
``BioLaySumm/BioLaySumm2025-*`` copies used here (same authors' shared task,
same train and validation splits) have no licence on their cards, so we rely
on the CC BY 4.0 of the underlying articles and of the authors' own card. We
download for local evaluation only and never commit the texts.

Download: the Hugging Face dataset viewer's ``/rows`` API (JSON pages of up
to 100 rows) through :class:`rbcore.http.PoliteFetcher`, so requests are
rate-limited, cached under ``data/`` and resumable. The tomasg25 copy is a
loading script that pulls two 425 MB zips from Google Drive, which is far
more than a sample needs. The test splits are not used: their lay summaries
are withheld.

The texts were sentence-tokenised and re-joined with spaces ("C . elegans
germline ."); :func:`detokenise` undoes the spacing so spaCy segments
sentences correctly.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlencode

from rbcore.http import PoliteFetcher

ROWS_API: Final = "https://datasets-server.huggingface.co/rows"
DATASET_API: Final = "https://huggingface.co/api/datasets/"
DATASETS: Final[Mapping[str, str]] = {
    "elife": "BioLaySumm/BioLaySumm2025-eLife",
    "plos": "BioLaySumm/BioLaySumm2025-PLOS",
}
PAGE_SIZE: Final = 100
"""The rows API's maximum page length."""

_SPLIT_DECIMAL = re.compile(r"(?<=\d) \. (?=\d)")
_SPACE_BEFORE = re.compile(r"\s+([,.;:!?%)\]}])")
_SPACE_AFTER = re.compile(r"([(\[{])\s+")
_SPACE_CLITIC = re.compile(r"\s+('s|'re|'ve|'ll|'d|n't|\u2019s)\b")
_MULTI_SPACE = re.compile(r"[ \t]+")


class DatasetFormatError(ValueError):
    """Raised when a downloaded page does not have the expected shape."""


@dataclass(frozen=True, slots=True)
class LayPair:
    """One article's abstract and lay summary.

    Attributes:
        id: ``<source>-<split>-<row>``, e.g. ``elife-validation-17``.
        source: "elife" or "plos".
        split: Dataset split.
        row: Row index in the split.
        title: Article title.
        year: Publication year as given.
        abstract: The technical abstract, detokenised.
        lay_summary: The lay summary, detokenised; paragraphs separated by
            blank lines.
    """

    id: str
    source: str
    split: str
    row: int
    title: str
    year: str
    abstract: str
    lay_summary: str


@dataclass(frozen=True, slots=True)
class Article:
    """A training-split article used to calibrate the reference statistics.

    Attributes:
        id: ``<source>-<split>-<row>``.
        source: "elife" or "plos".
        body_sections: Body sections after the abstract, still tokenised
            (one sentence per " ."-terminated run).
    """

    id: str
    source: str
    body_sections: tuple[str, ...]


def detokenise(text: str) -> str:
    """Undo the corpus's space-separated tokenisation.

    Args:
        text: Tokenised text ("the C . elegans germline ( Figure 1 ) .").

    Returns:
        Text with normal spacing ("the C. elegans germline (Figure 1)."), and
        decimals split by the tokeniser rejoined ("1 . 9" becomes "1.9").
    """
    text = _SPLIT_DECIMAL.sub(".", text)
    text = _SPACE_BEFORE.sub(r"\1", text)
    text = _SPACE_AFTER.sub(r"\1", text)
    text = _SPACE_CLITIC.sub(r"\1", text)
    return _MULTI_SPACE.sub(" ", text).strip()


def rows_url(dataset: str, split: str, offset: int, length: int = PAGE_SIZE) -> str:
    """Build a dataset-viewer rows URL.

    Args:
        dataset: Hugging Face dataset ID.
        split: Split name.
        offset: First row.
        length: Rows to fetch (at most :data:`PAGE_SIZE`).

    Returns:
        The URL.
    """
    query = urlencode(
        {
            "dataset": dataset,
            "config": "default",
            "split": split,
            "offset": offset,
            "length": length,
        }
    )
    return f"{ROWS_API}?{query}"


def fetch_rows(
    fetcher: PoliteFetcher, source: str, split: str, *, limit: int | None = None
) -> Iterator[tuple[int, Mapping[str, Any]]]:
    """Yield raw rows of one split, page by page (cached and resumable).

    Args:
        fetcher: The polite fetcher (its cache makes re-runs free).
        source: "elife" or "plos".
        split: Split name.
        limit: Stop after this many rows (None for the whole split).

    Yields:
        ``(row index, row fields)`` pairs. Rows the API returned with
        truncated cells are skipped, so no text is ever silently cut short.

    Raises:
        DatasetFormatError: If a page is not the expected JSON shape.
        KeyError: If ``source`` is unknown.
    """
    # Page through the split until its reported total (or the limit) is reached.
    dataset = DATASETS[source]
    offset = 0
    total: int | None = None
    while (total is None or offset < total) and (limit is None or offset < limit):
        length = PAGE_SIZE if limit is None else min(PAGE_SIZE, limit - offset)
        page = _parse_page(fetcher.get(rows_url(dataset, split, offset, length)))
        total = int(page["num_rows_total"])
        rows = page["rows"]
        if not rows:
            return

        # Skip rows with truncated cells rather than score cut-short text.
        for item in rows:
            if not item.get("truncated_cells"):
                yield int(item["row_idx"]), item["row"]
        offset += len(rows)


def _parse_page(body: bytes) -> Mapping[str, Any]:
    """Parse and check one rows-API page.

    Args:
        body: Response body.

    Returns:
        The parsed page.

    Raises:
        DatasetFormatError: If it is not JSON with ``rows`` and ``num_rows_total``.
    """
    try:
        page = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DatasetFormatError(f"rows page is not JSON: {exc}") from exc
    if not isinstance(page, dict) or "rows" not in page or "num_rows_total" not in page:
        raise DatasetFormatError("rows page lacks 'rows' or 'num_rows_total'")
    return page


def pair_from_row(source: str, split: str, row: int, fields: Mapping[str, Any]) -> LayPair | None:
    """Build a pair from one row, taking the abstract from the article's first section.

    Args:
        source: "elife" or "plos".
        split: Split name.
        row: Row index.
        fields: Row fields (``article``, ``summary``, ``section_headings``,
            ``title``, ``year``).

    Returns:
        The pair, or None if the first section is not headed "Abstract" or
        either text is empty.
    """
    # The abstract is the first section, and only if it is headed "Abstract".
    headings = fields.get("section_headings") or []
    sections = str(fields.get("article", "")).split("\n")
    if not headings or str(headings[0]).strip().lower() != "abstract":
        return None
    # Restore normal spacing; keep lay-summary paragraphs apart.
    abstract = detokenise(sections[0])
    paragraphs = (detokenise(p) for p in str(fields.get("summary", "")).split("\n"))
    lay_summary = "\n\n".join(p for p in paragraphs if p)
    if not abstract or not lay_summary:
        return None
    return LayPair(
        id=f"{source}-{split}-{row}",
        source=source,
        split=split,
        row=row,
        title=detokenise(str(fields.get("title", ""))),
        year=str(fields.get("year", "")),
        abstract=abstract,
        lay_summary=lay_summary,
    )


def article_from_row(source: str, split: str, row: int, fields: Mapping[str, Any]) -> Article:
    """Build a calibration article from one row (body sections only).

    Args:
        source: "elife" or "plos".
        split: Split name.
        row: Row index.
        fields: Row fields.

    Returns:
        The article; the first section (the abstract) is dropped.
    """
    sections = str(fields.get("article", "")).split("\n")
    return Article(
        id=f"{source}-{split}-{row}",
        source=source,
        body_sections=tuple(s for s in sections[1:] if s.strip()),
    )


def write_pairs(pairs: Sequence[LayPair], path: Path) -> None:
    """Write pairs as JSON Lines.

    Args:
        pairs: The pairs.
        path: Output file (parent directories are created).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for pair in pairs:
            handle.write(json.dumps(asdict(pair), ensure_ascii=False) + "\n")


def read_pairs(path: Path) -> list[LayPair]:
    """Read pairs written by :func:`write_pairs`.

    Args:
        path: JSON Lines file.

    Returns:
        The pairs, in file order.
    """
    with path.open(encoding="utf-8") as handle:
        return [LayPair(**json.loads(line)) for line in handle if line.strip()]


def dataset_revision(fetcher: PoliteFetcher, source: str) -> str | None:
    """Return the dataset's current commit on the Hub, for provenance.

    Args:
        fetcher: The polite fetcher.
        source: "elife" or "plos".

    Returns:
        The commit SHA, or None if the response has none.
    """
    info = json.loads(fetcher.get(DATASET_API + DATASETS[source], use_cache=False))
    sha = info.get("sha") if isinstance(info, dict) else None
    return str(sha) if sha else None
