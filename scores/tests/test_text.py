"""Tests for turning JATS and plain text into scorable units."""

from __future__ import annotations

from pathlib import Path

import pytest

from rbcore.jats import parse_jats
from rbscores.analysis import analyse_document
from rbscores.text import (
    MAX_PARAGRAPH_CHARS,
    MAX_TEXT_BYTES,
    ParagraphTooLongError,
    check_paragraph_lengths,
    document_from_article,
    document_from_text,
    load_document,
    single_paragraph_document,
)

SYNTHETIC_JATS = b"""<?xml version="1.0" encoding="UTF-8"?>
<article xmlns:xlink="http://www.w3.org/1999/xlink" article-type="research-article">
  <front><article-meta>
    <article-id pub-id-type="doi">10.0000/synthetic.1</article-id>
    <title-group><article-title>Synthetic article</article-title></title-group>
    <abstract><p>Synthetic abstract text.</p></abstract>
  </article-meta></front>
  <body>
    <p>A paragraph directly in the body.</p>
    <sec><title>Introduction</title>
      <p>First intro paragraph.</p>
      <sec><title>Background</title><p>Nested paragraph.</p></sec>
    </sec>
    <sec><title>Methods</title>
      <p>Methods paragraph.</p>
      <disp-formula><tex-math>x = y</tex-math></disp-formula>
    </sec>
  </body>
  <back><ack><p>Thanks to everyone.</p></ack></back>
</article>
"""


def test_jats_sections_are_abstracts_body_paragraphs_and_top_level_sections() -> None:
    """Synthetic JATS: nested sections fold into their top-level section."""
    document = document_from_article(parse_jats(SYNTHETIC_JATS))
    assert document.source == "jats"
    assert document.identifier == "10.0000/synthetic.1"
    assert [(s.id, s.kind, s.title) for s in document.sections] == [
        ("abs1", "abstract", None),
        ("body", "body", None),
        ("sec1", "body", "Introduction"),
        ("sec2", "body", "Methods"),
    ]
    intro = document.sections[2]
    assert [p.id for p in intro.paragraphs] == ["sec1-p1", "sec1.1-p1"]
    assert all(p.section_id == "sec1" for p in intro.paragraphs)


def test_jats_paper_unit_excludes_abstracts_back_matter_and_formulas() -> None:
    """The paper is the body; acknowledgements and display formulas are not scored."""
    document = document_from_article(parse_jats(SYNTHETIC_JATS))
    paper_ids = [p.id for s in document.paper_sections for p in s.paragraphs]
    assert paper_ids == ["body-p1", "sec1-p1", "sec1.1-p1", "sec2-p1"]
    all_text = " ".join(p.text for p in document.iter_paragraphs())
    assert "Thanks" not in all_text
    assert "x = y" not in all_text


def test_abstract_only_document_uses_the_abstract_as_the_paper() -> None:
    """With no body, the paper unit falls back to the abstracts."""
    xml = SYNTHETIC_JATS.replace(
        SYNTHETIC_JATS[SYNTHETIC_JATS.index(b"<body>") : SYNTHETIC_JATS.index(b"</body>") + 7], b""
    )
    document = document_from_article(parse_jats(xml))
    assert [s.id for s in document.paper_sections] == ["abs1"]


def test_plain_text_splits_on_blank_lines_and_collapses_whitespace() -> None:
    """Paragraph IDs are p1, p2, ... in one section."""
    document = document_from_text(
        "First  line\nstill first.\n\n\n  Second.  \n \nThird.", title="T"
    )
    assert [(p.id, p.text) for p in document.iter_paragraphs()] == [
        ("p1", "First line still first."),
        ("p2", "Second."),
        ("p3", "Third."),
    ]
    assert document.sections[0].title == "T"


def test_empty_text_has_no_sections() -> None:
    """Blank input gives an empty document."""
    assert document_from_text("  \n\n ").sections == ()


def test_single_paragraph_document_keeps_text_verbatim() -> None:
    """Offsets into the passage must stay valid, so whitespace is untouched."""
    text = "  Two  spaces\nand a newline. "
    document = single_paragraph_document(text, paragraph_id="q7")
    (paragraph,) = document.iter_paragraphs()
    assert paragraph.text == text
    assert paragraph.id == "q7"


def test_load_document_reads_real_jats_fixture(jats_fixtures: Path) -> None:
    """A real PLOS Medicine article (CC BY) loads with stable paragraph IDs."""
    document = load_document(jats_fixtures / "plos-pmed-1004542.xml")
    assert document.source == "jats"
    assert document.identifier == "10.1371/journal.pmed.1004542"
    assert "PLOS Medicine" in document.names
    assert any(s.kind == "abstract" for s in document.sections)
    body_ids = [p.id for s in document.paper_sections for p in s.paragraphs]
    assert body_ids
    assert all(pid.startswith(("sec", "body")) for pid in body_ids)


def test_jats_document_names_its_journal(jats_fixtures: Path) -> None:
    """The journal title and NLM abbreviation are recorded once each; text has none."""
    document = load_document(jats_fixtures / "elife-93719-pmc-s3.xml")
    assert document.names == ("eLife",)
    assert document_from_text("Some text.").names == ()


def test_load_document_reads_text_files(tmp_path: Path) -> None:
    """Non-XML files are read as UTF-8 text and named by file."""
    path = tmp_path / "note.txt"
    path.write_text("Hello there.\n\nGeneral Kenobi.", encoding="utf-8")
    document = load_document(path)
    assert document.identifier == "note.txt"
    assert len(document.iter_paragraphs()) == 2


def test_load_document_refuses_oversized_text(tmp_path: Path) -> None:
    """Text files above the size limit are refused before reading."""
    path = tmp_path / "big.txt"
    with path.open("wb") as handle:
        handle.truncate(MAX_TEXT_BYTES + 1)
    with pytest.raises(ValueError, match="larger than"):
        load_document(path)


def test_over_long_paragraph_gets_the_packages_own_error() -> None:
    """A paragraph over the cap is refused by name before spaCy sees it."""
    long_paragraph = "word " * (MAX_PARAGRAPH_CHARS // 5 + 1)
    document = document_from_text(f"A short first paragraph.\n\n{long_paragraph}")
    with pytest.raises(ParagraphTooLongError, match=r"paragraph p2 has [\d,]+ characters"):
        check_paragraph_lengths(document)

    # analyse_document refuses it before any pipeline is needed (none is passed here).
    with pytest.raises(ParagraphTooLongError):
        analyse_document(document)


def test_paragraph_at_the_cap_is_accepted() -> None:
    """A paragraph exactly at the cap passes the check."""
    document = single_paragraph_document("x" * MAX_PARAGRAPH_CHARS)
    check_paragraph_lengths(document)
