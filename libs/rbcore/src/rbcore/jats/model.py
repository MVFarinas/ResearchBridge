"""Typed, immutable data model for a parsed JATS article.

Identifier scheme (stable and deterministic, derived only from structural
position, so re-parsing the same article version yields the same IDs):

* ``body`` is the root of the main text. Its direct paragraphs are
  ``body-p1``, ``body-p2``, ...; its sections are ``sec1``, ``sec2``, ...;
  nested sections append ``.n`` (``sec2.1``, ``sec2.1.3``).
* Abstracts are ``abs1``, ``abs2``, ... in document order; abstract sections
  are ``abs1.sec1``, ``abs1.sec1.2``, ...
* Back matter (acknowledgements, appendices, back sections) is rooted at
  ``back``: ``back.sec1``, ``back.sec2.1``, ...
* A paragraph ID is its section ID plus ``-p`` and its 1-based position
  among that section's own paragraph blocks: ``sec2.1-p3``.
* Figures are ``fig1``, ``fig2``, ... and tables ``table1``, ... in document
  order across body and back matter.

The publisher's own ``@id`` attributes are kept as ``xml_id`` for reference,
but are not used as IDs because they are optional and inconsistent.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from rbcore.licences.model import PermissionsBlock


@dataclass(frozen=True, slots=True)
class Identifiers:
    """Article identifiers from ``article-meta/article-id``.

    Attributes:
        doi: DOI without any ``https://doi.org/`` prefix.
        pmcid: PMC ID with its ``PMC`` prefix.
        pmid: PubMed ID.
        publisher_id: The publisher's own article ID.
        other: Every other ``(pub-id-type, value)`` pair, in document order.
    """

    doi: str | None = None
    pmcid: str | None = None
    pmid: str | None = None
    publisher_id: str | None = None
    other: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class Author:
    """One contributor with ``contrib-type="author"``.

    Attributes:
        surname: Family name, if given as a structured name.
        given_names: Given names, if given.
        collab: Group-author name, for collaboration contributors.
        literal: Unstructured name text (``string-name``), when no
            structured ``name`` is given.
        orcid: ORCID iD URL or bare iD, as given.
        corresponding: Whether the contributor is marked corresponding.
    """

    surname: str | None = None
    given_names: str | None = None
    collab: str | None = None
    literal: str | None = None
    orcid: str | None = None
    corresponding: bool = False

    @property
    def display_name(self) -> str:
        """The name to show: group name, "Given Surname", or the literal name."""
        if self.collab:
            return self.collab
        structured = " ".join(part for part in (self.given_names, self.surname) if part)
        return structured or self.literal or ""


@dataclass(frozen=True, slots=True)
class Journal:
    """Journal metadata from ``journal-meta``.

    Attributes:
        title: Journal title.
        nlm_ta: NLM title abbreviation (``journal-id-type="nlm-ta"``).
        issns: All ISSNs, in document order.
        publisher: Publisher name.
    """

    title: str | None = None
    nlm_ta: str | None = None
    issns: tuple[str, ...] = ()
    publisher: str | None = None


@dataclass(frozen=True, slots=True)
class PublicationDate:
    """One ``pub-date`` element.

    Attributes:
        kind: ``@pub-type`` (epub, ppub, collection) or, for JATS 1.1+,
            ``@date-type`` with ``@publication-format`` (e.g. "pub/electronic").
        year: Year, if numeric.
        month: Month 1-12, if numeric or a month name.
        day: Day of month, if numeric.
    """

    kind: str
    year: int | None = None
    month: int | None = None
    day: int | None = None

    @property
    def iso(self) -> str | None:
        """The date as ISO 8601 at the precision available (YYYY[-MM[-DD]])."""
        if self.year is None:
            return None
        if self.month is None:
            return f"{self.year:04d}"
        if self.day is None:
            return f"{self.year:04d}-{self.month:02d}"
        return f"{self.year:04d}-{self.month:02d}-{self.day:02d}"


@dataclass(frozen=True, slots=True)
class Paragraph:
    """One paragraph-level block: the alignment unit for rewrites.

    Attributes:
        id: Stable positional ID, e.g. ``sec2.1-p3``.
        text: Plain text with inline markup flattened and whitespace
            normalised; citations and cross-references kept as their text.
        kind: "p", "list-item", "quote", "boxed", "def" or "formula".
        permissions: Every ``<permissions>`` block that applies to this block
            rather than the article licence: blocks on an enclosing
            ``disp-quote``, ``boxed-text``, ``statement`` or section
            (``sec-meta``), and blocks inside the paragraph itself (for
            example an inline quotation or graphic). Empty when it inherits
            the article licence. Pass to
            :func:`rbcore.licences.decide_part`.
        source_xml: The block's original XML, for rendering.
    """

    id: str
    text: str
    kind: str = "p"
    permissions: tuple[PermissionsBlock, ...] = ()
    source_xml: str = field(default="", repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class Section:
    """A section (or a root container such as ``body`` or an abstract).

    Attributes:
        id: Stable positional ID (see the module docstring).
        title: Section title text, if any.
        label: Section label such as "2.1", if any.
        kind: "body", "abstract", "back", "sec", "ack", "app" or "notes".
        sec_type: ``@sec-type`` (or ``@abstract-type`` for abstracts).
        xml_id: The publisher's ``@id``, if any.
        paragraphs: The section's own paragraph blocks, in order.
        sections: Nested sections, in order.
    """

    id: str
    title: str | None = None
    label: str | None = None
    kind: str = "sec"
    sec_type: str | None = None
    xml_id: str | None = None
    paragraphs: tuple[Paragraph, ...] = ()
    sections: tuple[Section, ...] = ()

    def iter_sections(self) -> Iterator[Section]:
        """Yield this section and every nested section, depth first.

        Yields:
            Sections in document order, starting with ``self``.
        """
        yield self
        for child in self.sections:
            yield from child.iter_sections()

    def iter_paragraphs(self) -> Iterator[Paragraph]:
        """Yield every paragraph in this section and its subsections.

        Yields:
            Paragraphs in document order.
        """
        for section in self.iter_sections():
            yield from section.paragraphs

    @property
    def text(self) -> str:
        """All paragraph text in the section tree, separated by blank lines."""
        return "\n\n".join(p.text for p in self.iter_paragraphs())


@dataclass(frozen=True, slots=True)
class Figure:
    """A figure (``fig``) or table (``table-wrap``) with its caption.

    Attributes:
        id: Stable positional ID: ``fig3`` or ``table2``.
        kind: "figure" or "table".
        label: Label such as "Figure 1", if any.
        caption_title: Caption title text, if any.
        caption: Caption paragraph text (title excluded), blank-line separated.
        section_id: ID of the section the object appears in.
        xml_id: The publisher's ``@id``, if any.
        permissions: Every ``<permissions>`` block that applies to the
            object: its own, one on an enclosing ``fig-group``,
            ``table-wrap-group``, box or section, and blocks on its
            ``graphic``, ``media`` or other content. Empty when it inherits
            the article licence. Pass to :func:`rbcore.licences.decide_part`,
            which fails closed when more than one applies.
        graphics: ``xlink:href`` of each ``graphic`` in the object.
        footnotes: Table footnote text (``table-wrap-foot``), tables only.
        source_xml: The object's original XML.
    """

    id: str
    kind: str
    label: str | None = None
    caption_title: str | None = None
    caption: str = ""
    section_id: str | None = None
    xml_id: str | None = None
    permissions: tuple[PermissionsBlock, ...] = ()
    graphics: tuple[str, ...] = ()
    footnotes: tuple[str, ...] = ()
    source_xml: str = field(default="", repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class FundingAward:
    """One ``award-group`` from a ``funding-group``.

    Attributes:
        sources: Funder names (``funding-source`` text).
        award_ids: Grant numbers (``award-id`` text).
    """

    sources: tuple[str, ...] = ()
    award_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Funding:
    """Funding information, kept as raw text for later appraisal.

    Attributes:
        statements: ``funding-statement`` text and funding sections/footnotes
            found in back matter, deduplicated, in document order.
        awards: Structured award groups from ``funding-group``.
    """

    statements: tuple[str, ...] = ()
    awards: tuple[FundingAward, ...] = ()

    @property
    def is_empty(self) -> bool:
        """Whether no funding information was found at all."""
        return not self.statements and not self.awards


@dataclass(frozen=True, slots=True)
class Article:
    """A parsed JATS article (main article only; ``sub-article`` is skipped).

    Attributes:
        identifiers: DOI, PMCID, PMID and other IDs.
        title: Article title.
        authors: Authors in document order.
        journal: Journal metadata.
        publication_dates: Every ``pub-date``, in document order.
        article_type: ``article/@article-type``.
        subject_heading: The ``subj-group-type="heading"`` subject, if any.
        language: ``article/@xml:lang``.
        abstracts: Every abstract (``abs1``...), including digests and
            ``abstract-type`` variants, in document order.
        body: The main text, rooted at ``body``.
        back: Back-matter sections, rooted at ``back``.
        figures: Figures in document order.
        tables: Tables in document order.
        permissions: The article's ``<permissions>`` block, if any.
        coi_statements: Conflict-of-interest statements, raw text.
        funding: Funding information, raw text.
        unattached_permissions: ``<permissions>`` blocks found in the main
            article that belong to nothing this model represents (for
            example on ``supplementary-material`` or a stray ``media``).
            Each one means part of the article is licensed differently in a
            way the parsed model cannot show, so any non-empty value should
            send the article to licence review.
    """

    identifiers: Identifiers
    title: str | None
    authors: tuple[Author, ...]
    journal: Journal
    publication_dates: tuple[PublicationDate, ...]
    article_type: str | None
    subject_heading: str | None
    language: str | None
    abstracts: tuple[Section, ...]
    body: Section
    back: Section
    figures: tuple[Figure, ...]
    tables: tuple[Figure, ...]
    permissions: PermissionsBlock | None
    coi_statements: tuple[str, ...]
    funding: Funding
    unattached_permissions: tuple[PermissionsBlock, ...] = ()

    @property
    def abstract(self) -> Section | None:
        """The main abstract: the first one without an ``abstract-type``.

        Falls back to the first abstract when every abstract is typed.
        """
        for abstract in self.abstracts:
            if abstract.sec_type is None:
                return abstract
        return self.abstracts[0] if self.abstracts else None

    @property
    def published(self) -> PublicationDate | None:
        """The best publication date: electronic, then print, then any."""
        preference = ("epub", "pub/electronic", "pub", "ppub", "pub/print", "collection")
        for kind in preference:
            for date in self.publication_dates:
                if date.kind == kind and date.year is not None:
                    return date
        return next((d for d in self.publication_dates if d.year is not None), None)

    def iter_paragraphs(self) -> Iterator[Paragraph]:
        """Yield every paragraph of the main text (body only), in order.

        Yields:
            Body paragraphs in document order.
        """
        return self.body.iter_paragraphs()

    def paragraph(self, paragraph_id: str) -> Paragraph:
        """Look up a paragraph anywhere in the article by its stable ID.

        Args:
            paragraph_id: An ID such as ``sec2.1-p3`` or ``abs1-p1``.

        Returns:
            The paragraph.

        Raises:
            KeyError: If no paragraph has that ID.
        """
        for root in (*self.abstracts, self.body, self.back):
            for paragraph in root.iter_paragraphs():
                if paragraph.id == paragraph_id:
                    return paragraph
        raise KeyError(paragraph_id)
