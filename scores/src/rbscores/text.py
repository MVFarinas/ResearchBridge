"""Text units to score: paragraphs grouped into sections, from JATS or plain text.

Scores are computed per paragraph, per section and per paper. For JATS input
the units come from :mod:`rbcore.jats`, so paragraph IDs are the stable
positional IDs shared with the benchmark passages and annotations
(``sec2.1-p3``). Sections are the abstracts and the top-level body sections
(each including its nested subsections); paragraphs that sit directly in
``<body>`` form a section with ID ``body``. The "paper" unit is the body only,
abstracts excluded, so the paper score describes the main text; abstracts are
still scored as their own sections, and definitions made in an abstract count
for the whole paper. Back matter (acknowledgements, appendices) and display
formulas are not scored.

Plain-text input is split into paragraphs on blank lines (IDs ``p1``, ``p2``,
...) inside a single section ``text``.

Scoring is not display: these functions read papers that may later fail the
§1.1 licence gate, and nothing here shows their text to anyone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rbcore.jats import Article, Section, parse_jats_file

_UNSCORED_PARAGRAPH_KINDS = frozenset({"formula"})
_BLANK_LINES = re.compile(r"\n\s*\n")
_WHITESPACE = re.compile(r"\s+")

MAX_TEXT_BYTES = 5 * 1024 * 1024
"""Largest plain-text file :func:`load_document` reads (about 40 long papers' worth)."""

MAX_PARAGRAPH_CHARS = 100_000
"""Longest paragraph the scores analyse.

A real paragraph is a few thousand characters. Anything near this is text
without paragraph breaks (often dumped from a PDF), whose parse would be slow
and whose sentence splitting would be unreliable; spaCy itself refuses texts
over 1,000,000 characters. Far below that limit, this keeps parsing memory
modest.
"""


class ParagraphTooLongError(ValueError):
    """Raised when a paragraph is longer than :data:`MAX_PARAGRAPH_CHARS`."""


@dataclass(frozen=True, slots=True)
class TextParagraph:
    """One paragraph to score.

    Attributes:
        id: Stable paragraph ID (``sec2.1-p3`` for JATS, ``p4`` for text).
        text: The paragraph text. Character offsets reported by the scores
            (term occurrences, definitions) index into this string.
        section_id: ID of the :class:`TextSection` it belongs to.
    """

    id: str
    text: str
    section_id: str


@dataclass(frozen=True, slots=True)
class TextSection:
    """A group of paragraphs scored together.

    Attributes:
        id: Section ID (``abs1``, ``sec2``, ``body`` or ``text``).
        title: Section title, if any.
        kind: "abstract", "body" or "text".
        paragraphs: The section's paragraphs in order, nested subsections included.
    """

    id: str
    title: str | None
    kind: str
    paragraphs: tuple[TextParagraph, ...]


@dataclass(frozen=True, slots=True)
class TextDocument:
    """A document reduced to scorable text units.

    Attributes:
        title: Document title, if known.
        sections: Sections in document order (abstracts first for JATS).
        source: "jats" or "text".
        identifier: DOI for JATS input when present, else the file name or None.
    """

    title: str | None
    sections: tuple[TextSection, ...]
    source: str
    identifier: str | None = None

    @property
    def paper_sections(self) -> tuple[TextSection, ...]:
        """The sections that make up the "paper" unit.

        Returns:
            Every non-abstract section; all sections if there are no others
            (an abstract-only document is still scorable).
        """
        main = tuple(s for s in self.sections if s.kind != "abstract")
        return main or self.sections

    def iter_paragraphs(self) -> tuple[TextParagraph, ...]:
        """Return every paragraph in every section, in document order.

        Returns:
            All paragraphs.
        """
        return tuple(p for section in self.sections for p in section.paragraphs)


def document_from_article(article: Article) -> TextDocument:
    """Reduce a parsed JATS article to scorable sections.

    Args:
        article: An article parsed by :func:`rbcore.jats.parse_jats`.

    Returns:
        Abstract sections, then a ``body`` section for paragraphs directly in
        the body (if any), then one section per top-level body section.
    """
    sections: list[TextSection] = []

    # Abstracts (including digests and author summaries) are their own sections.
    for abstract in article.abstracts:
        title = abstract.title or abstract.sec_type
        sections.append(_section_from(abstract, title=title, kind="abstract", flatten=True))

    # Paragraphs placed directly in <body> (no enclosing <sec>) form one section.
    if article.body.paragraphs:
        sections.append(_section_from(article.body, title=None, kind="body", flatten=False))

    # Each top-level body section absorbs its nested subsections.
    for child in article.body.sections:
        sections.append(_section_from(child, title=child.title, kind="body", flatten=True))

    non_empty = tuple(s for s in sections if s.paragraphs)
    return TextDocument(
        title=article.title,
        sections=non_empty,
        source="jats",
        identifier=article.identifiers.doi,
    )


def _section_from(section: Section, *, title: str | None, kind: str, flatten: bool) -> TextSection:
    """Build a :class:`TextSection` from an rbcore section.

    Args:
        section: The rbcore section.
        title: Title to record.
        kind: Section kind to record.
        flatten: Include nested subsections' paragraphs (True) or only the
            section's own paragraphs (False).

    Returns:
        The section, keeping only paragraphs with scorable prose.
    """
    source = section.iter_paragraphs() if flatten else iter(section.paragraphs)
    paragraphs = tuple(
        TextParagraph(id=p.id, text=p.text, section_id=section.id)
        for p in source
        if p.kind not in _UNSCORED_PARAGRAPH_KINDS and p.text.strip()
    )
    return TextSection(id=section.id, title=title, kind=kind, paragraphs=paragraphs)


def document_from_text(text: str, *, title: str | None = None) -> TextDocument:
    """Split plain text into paragraphs on blank lines.

    Whitespace inside each paragraph is collapsed to single spaces.

    Args:
        text: The text.
        title: Optional title.

    Returns:
        A document with one section ``text`` and paragraphs ``p1``, ``p2``, ...
    """
    chunks = (_WHITESPACE.sub(" ", chunk).strip() for chunk in _BLANK_LINES.split(text))
    paragraphs = tuple(
        TextParagraph(id=f"p{n}", text=chunk, section_id="text")
        for n, chunk in enumerate((c for c in chunks if c), start=1)
    )
    section = TextSection(id="text", title=title, kind="text", paragraphs=paragraphs)
    return TextDocument(title=title, sections=(section,) if paragraphs else (), source="text")


def single_paragraph_document(text: str, *, paragraph_id: str = "p1") -> TextDocument:
    """Wrap a text, unchanged, as a one-paragraph document.

    Unlike :func:`document_from_text`, whitespace is not normalised, so
    character offsets in the results index into ``text`` exactly. Used for
    human-study passages, whose marks are character offsets.

    Args:
        text: The text, used verbatim.
        paragraph_id: ID for the paragraph.

    Returns:
        A document with one section ``text`` holding one paragraph.
    """
    paragraph = TextParagraph(id=paragraph_id, text=text, section_id="text")
    section = TextSection(id="text", title=None, kind="text", paragraphs=(paragraph,))
    return TextDocument(title=None, sections=(section,), source="text")


def check_paragraph_lengths(document: TextDocument) -> None:
    """Refuse a document with a paragraph too long to analyse.

    Args:
        document: The document.

    Raises:
        ParagraphTooLongError: If any paragraph is longer than
            :data:`MAX_PARAGRAPH_CHARS`, naming the first such paragraph.
    """
    for paragraph in document.iter_paragraphs():
        if len(paragraph.text) > MAX_PARAGRAPH_CHARS:
            raise ParagraphTooLongError(
                f"paragraph {paragraph.id} has {len(paragraph.text):,} characters; the limit "
                f"is {MAX_PARAGRAPH_CHARS:,} (separate paragraphs with blank lines)"
            )


def load_document(path: str | Path) -> TextDocument:
    """Load a JATS XML file or a UTF-8 text file.

    Files ending in ``.xml`` or ``.nxml`` are parsed as JATS with
    :func:`rbcore.jats.parse_jats_file` (hardened parser); anything else is
    read as UTF-8 text.

    Args:
        path: File path.

    Returns:
        The document.

    Raises:
        rbcore.jats.JatsParseError: If a JATS file is malformed or unsafe.
        ValueError: If a text file is larger than :data:`MAX_TEXT_BYTES`.
        UnicodeDecodeError: If a text file is not UTF-8.
    """
    file_path = Path(path)
    if file_path.suffix.lower() in {".xml", ".nxml"}:
        return document_from_article(parse_jats_file(file_path))

    # Plain text: refuse oversized input before reading it into memory.
    if file_path.stat().st_size > MAX_TEXT_BYTES:
        raise ValueError(f"{file_path} is larger than {MAX_TEXT_BYTES} bytes")
    document = document_from_text(file_path.read_text(encoding="utf-8"), title=None)
    return TextDocument(
        title=document.title,
        sections=document.sections,
        source=document.source,
        identifier=file_path.name,
    )
