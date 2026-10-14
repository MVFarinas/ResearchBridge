"""Tests for validation 1's data preparation and calibration (synthetic hub, no network)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from spacy.language import Language

from rbcore.http import PoliteFetcher, RateLimiter
from rbscores.familiarity import WordfreqFamiliarity
from rbscores.readability.features import FEATURE_NAMES
from rbscores.validation1.calibrate import body_windows, compute_reference
from rbscores.validation1.dataset import (
    Article,
    DatasetFormatError,
    LayPair,
    article_from_row,
    dataset_revision,
    detokenise,
    fetch_rows,
    pair_from_row,
    read_pairs,
    rows_url,
    write_pairs,
)


@pytest.mark.parametrize(
    ("tokenised", "expected"),
    [
        ("In the C . elegans germline ( Figure 1 ) .", "In the C. elegans germline (Figure 1)."),
        ("More than 1 . 9 billion , or 50 % .", "More than 1.9 billion, or 50%."),
        ("The cell 's wall did n't break .", "The cell's wall didn't break."),
        ("A  [ 12 ]  ;  B", "A [12]; B"),
    ],
)
def test_detokenise(tokenised: str, expected: str) -> None:
    """Spaces the corpus put around punctuation are removed."""
    assert detokenise(tokenised) == expected


def test_rows_url_encodes_the_query() -> None:
    """The rows URL names the dataset, split, offset and length."""
    url = rows_url("BioLaySumm/BioLaySumm2025-eLife", "validation", 200, 50)
    parts = urlsplit(url)
    assert parts.netloc == "datasets-server.huggingface.co"
    assert parse_qs(parts.query) == {
        "dataset": ["BioLaySumm/BioLaySumm2025-eLife"],
        "config": ["default"],
        "split": ["validation"],
        "offset": ["200"],
        "length": ["50"],
    }


def test_fetch_rows_pages_skips_truncated_rows_and_honours_limit(
    synthetic_hub: PoliteFetcher,
) -> None:
    """Truncated rows are never yielded; a limit stops early."""
    rows = list(fetch_rows(synthetic_hub, "elife", "validation"))
    assert [index for index, _ in rows] == [0, 1, 3]
    limited = list(fetch_rows(synthetic_hub, "elife", "validation", limit=2))
    assert [index for index, _ in limited] == [0, 1]


def test_fetch_rows_rejects_malformed_pages(tmp_path: Path) -> None:
    """A page that is not the rows-API shape raises."""
    fetcher = PoliteFetcher(
        cache_dir=None,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"oops": 1})),
        rate_limiter=RateLimiter(default_interval=0.0),
    )
    with fetcher, pytest.raises(DatasetFormatError, match="rows"):
        list(fetch_rows(fetcher, "plos", "validation"))


def test_pair_from_row_takes_the_first_section_as_abstract() -> None:
    """The abstract is the article's first section; summary paragraphs are kept apart."""
    fields = {
        "article": "Tech abstract ( TA ) .\nIntro text .",
        "summary": "Lay one .\nLay two .",
        "section_headings": ["Abstract", "Introduction"],
        "title": "A title",
        "year": "2019",
    }
    pair = pair_from_row("plos", "validation", 7, fields)
    assert pair == LayPair(
        id="plos-validation-7",
        source="plos",
        split="validation",
        row=7,
        title="A title",
        year="2019",
        abstract="Tech abstract (TA).",
        lay_summary="Lay one.\n\nLay two.",
    )


def test_pair_from_row_rejects_rows_without_an_abstract_or_summary() -> None:
    """Rows whose first heading is not "Abstract", or with no summary, are skipped."""
    base = {"article": "x .\ny .", "summary": "s .", "section_headings": ["Abstract", "B"]}
    assert pair_from_row("elife", "validation", 0, base | {"section_headings": ["Intro"]}) is None
    assert pair_from_row("elife", "validation", 0, base | {"summary": ""}) is None
    assert pair_from_row("elife", "validation", 0, base | {"section_headings": []}) is None


def test_article_from_row_drops_the_abstract() -> None:
    """Calibration articles keep only body sections."""
    article = article_from_row("elife", "train", 3, {"article": "abs .\nintro .\n\nresults ."})
    assert article == Article(
        id="elife-train-3", source="elife", body_sections=("intro .", "results .")
    )


def test_pairs_round_trip(tmp_path: Path) -> None:
    """Pairs written as JSON Lines read back identically."""
    pairs = [
        LayPair("elife-validation-1", "elife", "validation", 1, "T", "2020", "Abs.", "Lay."),
        LayPair("plos-validation-2", "plos", "validation", 2, "Ü", "2021", "A2.", "L2."),
    ]
    path = tmp_path / "deep" / "pairs.jsonl"
    write_pairs(pairs, path)
    assert read_pairs(path) == pairs


def test_dataset_revision(synthetic_hub: PoliteFetcher) -> None:
    """The dataset's commit SHA is read from the Hub API."""
    assert dataset_revision(synthetic_hub, "plos") == "synthetic-sha"


def test_body_windows_take_whole_sentences_from_each_section() -> None:
    """Each section contributes its opening window of whole sentences, up to the limit."""
    sentence = "One two three four five six seven eight nine ."
    section = " ".join([sentence] * 30)
    article = Article("x", "elife", (section, section, "Too short .", section))
    windows = body_windows(article, window_words=50, max_windows=2)
    assert len(windows) == 2
    assert all(w.endswith("nine.") for w in windows)
    assert len(windows[0].split()) == 45  # 5 sentences of 10 tokens, after detokenising
    assert body_windows(Article("y", "plos", ("Too short .",)), window_words=50) == []


def test_compute_reference(nlp: Language) -> None:
    """Reference statistics are the mean and sample SD of each feature."""
    texts = ["The cat sat. The dog ran far away.", "Birds fly south in the cold winter months."]
    reference = compute_reference(
        texts, nlp=nlp, familiarity=WordfreqFamiliarity(), version="v-test", description="SYNTHETIC"
    )
    assert reference.units == 2
    assert set(reference.features) == set(FEATURE_NAMES)
    # Mean sentence lengths are (3 + 5) / 2 = 4 and 8: mean 6, sample SD sqrt(8).
    assert reference.features["mean_sentence_length"].mean == pytest.approx(6.0)
    assert reference.features["mean_sentence_length"].sd == pytest.approx(8**0.5)
    with pytest.raises(ValueError, match="at least 2"):
        compute_reference(
            ["Only one."], nlp=nlp, familiarity=WordfreqFamiliarity(), version="v", description="d"
        )
