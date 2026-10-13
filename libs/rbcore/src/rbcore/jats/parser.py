"""Parse JATS XML (PMC, Europe PMC, PLOS, eLife) safely into :class:`Article`.

Safety: input is untrusted. The lxml parser is configured to never resolve
entities, never load a DTD and never touch the network, which blocks XXE,
entity-expansion ("billion laughs") and DTD-fetch attacks. Parsing is strict:
malformed XML raises :class:`JatsParseError` rather than being silently
"recovered", because recovery can drop elements such as a figure's own
``<permissions>`` block and so widen what the licence gate allows.

Only the main article (``front``, ``body``, ``back``, ``floats-group``) is
parsed; ``sub-article`` elements (eLife peer-review material and similar) are
skipped.

Licence safety: every ``<permissions>`` block in the main article is either
attached to the part it covers (the article, a figure or table, or a
paragraph block) or reported in :attr:`Article.unattached_permissions`, so
no block is ever silently dropped.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from lxml import etree

from rbcore.jats.model import (
    Article,
    Author,
    Figure,
    Funding,
    FundingAward,
    Identifiers,
    Journal,
    Paragraph,
    PublicationDate,
    Section,
)
from rbcore.jats.text import flatten, local_name, normalise_whitespace
from rbcore.licences.model import AliLicenceRef, LicenceStatement, PermissionsBlock

DEFAULT_MAX_BYTES = 50 * 1024 * 1024

_XLINK_HREF = "{http://www.w3.org/1999/xlink}href"
_XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_ALI_NS = "http://www.niso.org/schemas/ali/1.0/"

# Root containers get "sec{n}" children; sections nest as "sec1.2".
_ROOT_KINDS = frozenset({"body", "abstract", "back"})
# Back-matter children that are kept as sections (ref-list and fn-group are not).
_BACK_SECTION_KINDS = frozenset({"sec", "ack", "app", "notes"})
# Floating objects (and their groups) that are parsed as Figure records.
_FLOAT_NAMES = frozenset({"fig", "fig-group", "table-wrap", "table-wrap-group"})
# Ancestors at which the search for enclosing permissions stops: the article
# licence lives in article-meta and is never a part-level override.
_PERMISSIONS_SEARCH_STOP = frozenset({"article", "sub-article", "front", "article-meta"})

_COI_FN_TYPES = frozenset(
    {
        "coi-statement",
        "conflict",
        "conflict-of-interest",
        "conflicts-of-interest",
        "competing-interest",
        "competing-interests",
    }
)
_COI_TITLE = re.compile(
    r"\b(competing\s+interests?|conflicts?\s+of\s+interests?|declarations?\s+of\s+interests?"
    r"|duality\s+of\s+interests?|disclosures?)\b",
    re.IGNORECASE,
)
_FUNDING_TYPES = frozenset({"funding", "financial-disclosure", "funding-information"})
_FUNDING_TITLE = re.compile(r"\b(funding|financial\s+(support|disclosure))\b", re.IGNORECASE)

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}


class JatsParseError(ValueError):
    """Raised when input is not well-formed JATS that this parser can read."""


def parse_jats(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> Article:
    """Parse a JATS document.

    Args:
        data: The raw XML bytes (bytes, not str, so the XML declaration's
            encoding is honoured).
        max_bytes: Refuse larger inputs.

    Returns:
        The parsed article.

    Raises:
        JatsParseError: If the input is too large, not well-formed, contains
            an entity reference other than the five predefined XML entities
            (internal-subset and DTD entities are never resolved, so their
            text would otherwise be lost), or is not a JATS ``article``.
    """
    if len(data) > max_bytes:
        raise JatsParseError(f"input is {len(data)} bytes, over the {max_bytes}-byte limit")
    try:
        # Safe by construction: see _safe_parser for the hardened options.
        root = etree.fromstring(data, parser=_safe_parser())
    except etree.XMLSyntaxError as exc:
        raise JatsParseError(f"not well-formed XML: {exc}") from exc
    # Entities are never resolved, so a reference left in the tree would make
    # its text vanish silently; refuse the document instead.
    entity = next(root.iter(etree.Entity), None)
    if entity is not None:
        raise JatsParseError(
            f"unresolved entity reference {entity.text} (DTD-declared entities are not supported)"
        )
    return _ArticleParser(_article_root(root)).parse()


def parse_jats_file(path: str | Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> Article:
    """Parse a JATS file from disk.

    Args:
        path: Path to the XML file.
        max_bytes: Refuse larger files (checked before reading).

    Returns:
        The parsed article.

    Raises:
        JatsParseError: As for :func:`parse_jats`.
        OSError: If the file cannot be read.
    """
    file_path = Path(path)
    size = file_path.stat().st_size
    if size > max_bytes:
        raise JatsParseError(f"{file_path} is {size} bytes, over the {max_bytes}-byte limit")
    return parse_jats(file_path.read_bytes(), max_bytes=max_bytes)


def _safe_parser() -> etree.XMLParser:
    """Build an lxml parser that cannot be made to expand or fetch anything.

    Returns:
        A strict parser with entity resolution, DTD loading and network
        access all disabled, and comments and processing instructions dropped.
    """
    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        recover=False,
        remove_comments=True,
        remove_pis=True,
        # Leave collect_ids at its default: with libxml2 2.14, collect_ids=False
        # makes the parser try to load the external DTD.
    )


def _article_root(root: etree._Element) -> etree._Element:
    """Return the ``article`` element, unwrapping a ``pmc-articleset`` if needed.

    Args:
        root: The document's root element.

    Returns:
        The main ``article`` element.

    Raises:
        JatsParseError: If no ``article`` element is found.
    """
    if local_name(root) == "article":
        return root
    if local_name(root) == "pmc-articleset":
        article = _child(root, "article")
        if article is not None:
            return article
    raise JatsParseError(f"root element is <{local_name(root)}>, expected <article>")


def _children(element: etree._Element | None, *names: str) -> Iterator[etree._Element]:
    """Yield direct children whose local name is one of ``names``.

    Args:
        element: The parent, or None (yields nothing).
        *names: Local names to match.

    Yields:
        Matching children in document order.
    """
    if element is None:
        return
    for child in element:
        if local_name(child) in names:
            yield child


def _child(element: etree._Element | None, *names: str) -> etree._Element | None:
    """Return the first direct child whose local name is one of ``names``.

    Args:
        element: The parent, or None.
        *names: Local names to match.

    Returns:
        The first match, or None.
    """
    return next(_children(element, *names), None)


def _text(element: etree._Element | None, *, skip: tuple[str, ...] = ()) -> str | None:
    """Flatten an optional element, mapping empty text to None.

    Args:
        element: The element, or None.
        skip: Extra local names to omit.

    Returns:
        Plain text, or None if the element is absent or empty.
    """
    if element is None:
        return None
    return flatten(element, skip=skip) or None


def _dedupe(items: list[str]) -> tuple[str, ...]:
    """Drop empty and repeated strings, keeping first occurrences in order.

    Args:
        items: Strings in document order.

    Returns:
        The unique non-empty strings.
    """
    return tuple(dict.fromkeys(item for item in items if item))


def parse_permissions(element: etree._Element) -> PermissionsBlock:
    """Parse a ``<permissions>`` block, keeping each licence field separate.

    Args:
        element: A JATS ``permissions`` element.

    Returns:
        The raw permissions block; nothing is interpreted here. Its
        ``context`` names the element it is attached to (the parent, or the
        section for a block inside ``sec-meta``).
    """
    statements: list[LicenceStatement] = []
    for licence in _children(element, "license"):
        prose = [flatten(p) for p in _children(licence, "license-p")]
        statements.append(
            LicenceStatement(
                xlink_href=(licence.get(_XLINK_HREF) or licence.get("href") or "").strip() or None,
                ali_license_refs=_ali_refs(licence),
                license_type=licence.get("license-type"),
                prose=" ".join(p for p in prose if p) or None,
            )
        )
    # ali:license_ref may also sit directly in <permissions> (JATS 1.1+).
    direct_refs = _ali_refs(element)
    if direct_refs:
        statements.append(LicenceStatement(ali_license_refs=direct_refs))
    free_to_read = _child(element, "free_to_read")
    return PermissionsBlock(
        copyright_statement=_text(_child(element, "copyright-statement")),
        copyright_years=_dedupe([flatten(e) for e in _children(element, "copyright-year")]),
        copyright_holders=_dedupe([flatten(e) for e in _children(element, "copyright-holder")]),
        licences=tuple(statements),
        free_to_read=free_to_read is not None,
        free_to_read_start_date=_ali_attribute(free_to_read, "start_date"),
        free_to_read_end_date=_ali_attribute(free_to_read, "end_date"),
        context=_permissions_context(element),
    )


def _ali_refs(element: etree._Element) -> tuple[AliLicenceRef, ...]:
    """Read the ``ali:license_ref`` children of an element.

    Args:
        element: A ``license`` or ``permissions`` element.

    Returns:
        One reference per child, with its ``@specific-use`` and ALI dates.
    """
    return tuple(
        AliLicenceRef(
            value=normalise_whitespace("".join(ref.itertext())),
            specific_use=ref.get("specific-use"),
            start_date=_ali_attribute(ref, "start_date"),
            end_date=_ali_attribute(ref, "end_date"),
        )
        for ref in _children(element, "license_ref")
    )


def _ali_attribute(element: etree._Element | None, name: str) -> str | None:
    """Read an ALI attribute, which feeds write with or without the ALI namespace.

    Args:
        element: The element, or None.
        name: Attribute local name, e.g. "start_date".

    Returns:
        The stripped value, or None if absent or empty.
    """
    if element is None:
        return None
    value = element.get(name) or element.get(f"{{{_ALI_NS}}}{name}") or ""
    return value.strip() or None


def _permissions_context(element: etree._Element) -> str | None:
    """Name the element a ``<permissions>`` block is attached to.

    Args:
        element: A ``permissions`` element.

    Returns:
        The parent's local name ("sec" for a block inside ``sec-meta``), or
        None for a detached block.
    """
    parent = element.getparent()
    if parent is not None and local_name(parent) == "sec-meta":
        parent = parent.getparent()
    return local_name(parent) if parent is not None else None


def _direct_permissions(element: etree._Element) -> list[etree._Element]:
    """Return the permissions blocks attached directly to an element.

    Args:
        element: Any element.

    Returns:
        Its ``permissions`` children, then those inside its ``sec-meta``.
    """
    return [
        *_children(element, "permissions"),
        *_children(_child(element, "sec-meta"), "permissions"),
    ]


def _inside_nested_float(node: etree._Element, root: etree._Element) -> bool:
    """Whether ``node`` sits inside a figure or table nested within ``root``.

    Args:
        node: A descendant of ``root``.
        root: The part being examined.

    Returns:
        True if an ancestor of ``node`` below ``root`` is a float or float
        group (those blocks belong to that float, not to ``root``).
    """
    for ancestor in node.iterancestors():
        if ancestor is root:
            return False
        if local_name(ancestor) in _FLOAT_NAMES:
            return True
    return False


class _ArticleParser:
    """Single-use parser holding the per-document counters and section map."""

    def __init__(self, article: etree._Element) -> None:
        """Prepare to parse one article.

        Args:
            article: The ``article`` element.
        """
        self._article = article
        self._front = _child(article, "front")
        self._meta = _child(self._front, "article-meta")
        self._body = _child(article, "body")
        self._back = _child(article, "back")
        self._floats_group = _child(article, "floats-group")
        # Maps each parsed section element to its stable ID, so figures can
        # find the section they sit in.
        self._section_ids: dict[etree._Element, str] = {}
        # Every <permissions> element attached to a part of the model; the
        # rest are reported as unattached so none is silently dropped.
        self._attached: set[etree._Element] = set()

    def parse(self) -> Article:
        """Parse the whole article.

        Returns:
            The parsed article.
        """
        # Sections are parsed before floats so each figure can find its section.
        abstracts = tuple(
            self._parse_section(element, f"abs{n}", "abstract", element.get("abstract-type"))
            for n, element in enumerate(_children(self._meta, "abstract"), start=1)
        )
        body = (
            self._parse_section(self._body, "body", "body")
            if self._body is not None
            else Section(id="body", kind="body")
        )
        back = self._parse_back()
        figures, tables = self._parse_floats()
        permissions_element = _child(self._meta, "permissions")
        if permissions_element is not None:
            self._attached.add(permissions_element)
        return Article(
            identifiers=self._identifiers(),
            title=_text(_child(_child(self._meta, "title-group"), "article-title")),
            authors=self._authors(),
            journal=self._journal(),
            publication_dates=self._publication_dates(),
            article_type=self._article.get("article-type"),
            subject_heading=self._subject_heading(),
            language=self._article.get(_XML_LANG),
            abstracts=abstracts,
            body=body,
            back=back,
            figures=figures,
            tables=tables,
            permissions=(
                parse_permissions(permissions_element) if permissions_element is not None else None
            ),
            coi_statements=self._coi_statements(),
            funding=self._funding(),
            unattached_permissions=self._unattached_permissions(),
        )

    # ----- part-level permissions --------------------------------------

    def _part_permissions(self, element: etree._Element) -> tuple[PermissionsBlock, ...]:
        """Collect every permissions block that applies to one part.

        A block applies if it is attached to an enclosing element (a
        ``fig-group``, ``disp-quote``, ``boxed-text``, section ``sec-meta``,
        ...) or sits anywhere inside the part itself (on a ``graphic``,
        ``media``, inline quotation, or directly), except inside a nested
        figure or table, which owns its blocks.

        Args:
            element: The figure, table or paragraph-block element.

        Returns:
            Parsed blocks, outermost first, then those inside the part.
        """
        # Enclosing blocks, walking up to (not into) the article-level metadata.
        enclosing: list[etree._Element] = []
        for ancestor in element.iterancestors():
            if local_name(ancestor) in _PERMISSIONS_SEARCH_STOP:
                break
            enclosing[:0] = _direct_permissions(ancestor)
        # Blocks inside the part itself, wherever they are nested.
        inside = [
            node
            for node in element.iter()
            if local_name(node) == "permissions" and not _inside_nested_float(node, element)
        ]
        found = [*enclosing, *inside]
        self._attached.update(found)
        return tuple(parse_permissions(node) for node in found)

    def _unattached_permissions(self) -> tuple[PermissionsBlock, ...]:
        """Report permissions blocks in the main article that no part claimed.

        Must run after every part has been parsed.

        Returns:
            The unclaimed blocks in document order (``sub-article`` excluded).
        """
        unattached: list[PermissionsBlock] = []
        for container in self._article:
            if local_name(container) == "sub-article":
                continue
            unattached.extend(
                parse_permissions(node)
                for node in container.iter()
                if local_name(node) == "permissions" and node not in self._attached
            )
        return tuple(unattached)

    # ----- front matter -------------------------------------------------

    def _identifiers(self) -> Identifiers:
        """Collect article IDs, normalising DOI and PMCID forms.

        Returns:
            The identifiers; the first value of each type wins.
        """
        found: dict[str, str] = {}
        other: list[tuple[str, str]] = []
        for element in _children(self._meta, "article-id"):
            id_type = (element.get("pub-id-type") or "").lower()
            value = normalise_whitespace("".join(element.itertext()))
            if not value:
                continue
            # Older PMC XML uses pub-id-type="pmc" with bare digits.
            if id_type in {"pmc", "pmcid"}:
                id_type, value = (
                    "pmcid",
                    value if value.upper().startswith("PMC") else f"PMC{value}",
                )
            if id_type == "doi":
                value = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", value, flags=re.IGNORECASE)
            if id_type in {"doi", "pmcid", "pmid", "publisher-id"}:
                found.setdefault(id_type, value)
            else:
                other.append((id_type, value))
        return Identifiers(
            doi=found.get("doi"),
            pmcid=found.get("pmcid"),
            pmid=found.get("pmid"),
            publisher_id=found.get("publisher-id"),
            other=tuple(other),
        )

    def _authors(self) -> tuple[Author, ...]:
        """Collect authors from every ``contrib-group`` in ``article-meta``.

        Returns:
            Authors in document order. Contributors without a
            ``contrib-type`` are treated as authors.
        """
        authors: list[Author] = []
        for group in _children(self._meta, "contrib-group"):
            for contrib in _children(group, "contrib"):
                if (contrib.get("contrib-type") or "author").lower() != "author":
                    continue
                # lxml elements are falsy when childless, so never chain them with `or`.
                name = _child(contrib, "name")
                if name is None:
                    name = _child(_child(contrib, "name-alternatives"), "name")
                orcid = next(
                    (
                        normalise_whitespace("".join(e.itertext()))
                        for e in _children(contrib, "contrib-id")
                        if (e.get("contrib-id-type") or "").lower() == "orcid"
                    ),
                    None,
                )
                corresponding = contrib.get("corresp") == "yes" or any(
                    x.get("ref-type") == "corresp" for x in _children(contrib, "xref")
                )
                # Unstructured names keep their text; structured parts are used if present.
                string_name = _child(contrib, "string-name") if name is None else None
                parts = name if name is not None else string_name
                authors.append(
                    Author(
                        surname=_text(_child(parts, "surname")),
                        given_names=_text(_child(parts, "given-names")),
                        # A collab may list its members in a nested contrib-group.
                        collab=_text(_child(contrib, "collab"), skip=("contrib-group",)),
                        literal=_text(string_name),
                        orcid=orcid,
                        corresponding=corresponding,
                    )
                )
        return tuple(authors)

    def _journal(self) -> Journal:
        """Collect journal metadata.

        Returns:
            The journal.
        """
        meta = _child(self._front, "journal-meta")
        # JATS 3.0+ wraps the title in journal-title-group; older NLM DTDs do not.
        title = _child(_child(meta, "journal-title-group"), "journal-title")
        if title is None:
            title = _child(meta, "journal-title")
        # The NLM title abbreviation is one journal-id among several types.
        nlm_ta = next(
            (
                flatten(e)
                for e in _children(meta, "journal-id")
                if e.get("journal-id-type") == "nlm-ta"
            ),
            None,
        )
        return Journal(
            title=_text(title),
            nlm_ta=nlm_ta,
            issns=_dedupe([flatten(e) for e in _children(meta, "issn")]),
            publisher=_text(_child(_child(meta, "publisher"), "publisher-name")),
        )

    def _publication_dates(self) -> tuple[PublicationDate, ...]:
        """Collect every ``pub-date`` in ``article-meta``.

        Returns:
            Dates in document order.
        """
        dates: list[PublicationDate] = []
        for element in _children(self._meta, "pub-date"):
            kind = element.get("pub-type")
            if kind is None:
                date_type = element.get("date-type", "pub")
                pub_format = element.get("publication-format")
                kind = f"{date_type}/{pub_format}" if pub_format else date_type
            dates.append(
                PublicationDate(
                    kind=kind,
                    year=_int(_text(_child(element, "year"))),
                    month=_month(_text(_child(element, "month"))),
                    day=_int(_text(_child(element, "day"))),
                )
            )
        return tuple(dates)

    def _subject_heading(self) -> str | None:
        """Return the ``subj-group-type="heading"`` subject, if any.

        Returns:
            The heading subject text, or None.
        """
        for group in _children(_child(self._meta, "article-categories"), "subj-group"):
            if group.get("subj-group-type") == "heading":
                return _text(_child(group, "subject"))
        return None

    # ----- sections and paragraphs -------------------------------------

    def _parse_back(self) -> Section:
        """Parse back matter into a ``back`` root section.

        Returns:
            The back section; acknowledgements, appendices, notes and
            back sections become its subsections, in document order.
        """
        sections: list[Section] = []
        if self._back is not None:
            self._section_ids[self._back] = "back"
            for element in self._back:
                name = local_name(element)
                # Appendices are wrapped in app-group; flatten that wrapper.
                candidates = list(_children(element, "app")) if name == "app-group" else [element]
                for candidate in candidates:
                    kind = local_name(candidate)
                    if kind in _BACK_SECTION_KINDS:
                        section_id = f"back.sec{len(sections) + 1}"
                        sections.append(
                            self._parse_section(
                                candidate, section_id, kind, candidate.get("sec-type")
                            )
                        )
        return Section(id="back", kind="back", sections=tuple(sections))

    def _parse_section(
        self,
        element: etree._Element,
        section_id: str,
        kind: str,
        sec_type: str | None = None,
    ) -> Section:
        """Parse a section-like element and its nested sections.

        Args:
            element: The ``sec``, ``body``, ``abstract``, ``ack``, ``app``
                or ``notes`` element.
            section_id: Its stable ID.
            kind: Section kind recorded on the result.
            sec_type: ``@sec-type`` or ``@abstract-type``.

        Returns:
            The parsed section.
        """
        self._section_ids[element] = section_id
        # Nested sections recurse; every other child may become paragraph blocks.
        blocks: list[tuple[etree._Element, str, str]] = []
        subsections: list[Section] = []
        for child in element:
            name = local_name(child)
            if name == "sec":
                child_id = self._child_section_id(section_id, kind, len(subsections) + 1)
                subsections.append(
                    self._parse_section(child, child_id, "sec", child.get("sec-type"))
                )
            elif name not in {"title", "label"}:
                blocks.extend(_blocks(child, name))

        # A block's position within its section is its stable ID.
        paragraphs = tuple(
            Paragraph(
                id=f"{section_id}-p{n}",
                text=text,
                kind=block_kind,
                permissions=self._part_permissions(source),
                source_xml=etree.tostring(source, encoding="unicode", with_tail=False),
            )
            for n, (source, block_kind, text) in enumerate(blocks, start=1)
        )
        return Section(
            id=section_id,
            title=_text(_child(element, "title")),
            label=_text(_child(element, "label")),
            kind=kind,
            sec_type=sec_type,
            xml_id=element.get("id"),
            paragraphs=paragraphs,
            sections=tuple(subsections),
        )

    @staticmethod
    def _child_section_id(parent_id: str, parent_kind: str, position: int) -> str:
        """Compute a nested section's stable ID.

        Args:
            parent_id: The parent section's ID.
            parent_kind: The parent's kind.
            position: 1-based position among the parent's subsections.

        Returns:
            ``sec{n}`` under ``body``, ``{root}.sec{n}`` under other roots,
            ``{parent}.{n}`` under a section.
        """
        if parent_kind == "body":
            return f"sec{position}"
        if parent_kind in _ROOT_KINDS:
            return f"{parent_id}.sec{position}"
        return f"{parent_id}.{position}"

    # ----- figures and tables ------------------------------------------

    def _parse_floats(self) -> tuple[tuple[Figure, ...], tuple[Figure, ...]]:
        """Collect every figure and table in body, back matter and floats-group.

        Returns:
            ``(figures, tables)``, each in document order.
        """
        figures: list[Figure] = []
        tables: list[Figure] = []
        # Document order across body, back, then floats-group (which JATS
        # places after back) gives the stable fig/table numbers.
        for container in (self._body, self._back, self._floats_group):
            if container is None:
                continue
            for element in container.iter():
                name = local_name(element)
                if name == "fig":
                    figures.append(self._parse_float(element, f"fig{len(figures) + 1}", "figure"))
                elif name == "table-wrap":
                    tables.append(self._parse_float(element, f"table{len(tables) + 1}", "table"))
        return tuple(figures), tuple(tables)

    def _parse_float(self, element: etree._Element, float_id: str, kind: str) -> Figure:
        """Parse one figure or table.

        Args:
            element: The ``fig`` or ``table-wrap`` element.
            float_id: Its stable ID.
            kind: "figure" or "table".

        Returns:
            The parsed object, with every permissions block that applies to it.
        """
        # Captions normally hold <p> elements; some publishers put text directly in <caption>.
        caption = _child(element, "caption")
        caption_paragraphs = [flatten(p) for p in _children(caption, "p")]
        if not caption_paragraphs and caption is not None:
            caption_paragraphs = [flatten(caption, skip=("title",))]
        # Table footnotes: one entry per <fn>, or the whole foot when it has none.
        footnotes: list[str] = []
        for foot in _children(element, "table-wrap-foot"):
            notes = [flatten(fn, skip=("label",)) for fn in foot.iter() if local_name(fn) == "fn"]
            footnotes.extend(notes or [flatten(foot)])
        return Figure(
            id=float_id,
            kind=kind,
            label=_text(_child(element, "label")),
            caption_title=_text(_child(caption, "title")),
            caption="\n\n".join(p for p in caption_paragraphs if p),
            section_id=self._enclosing_section(element) or self._citing_section(element.get("id")),
            xml_id=element.get("id"),
            permissions=self._part_permissions(element),
            graphics=tuple(
                href
                for g in element.iter()
                if local_name(g) == "graphic" and (href := g.get(_XLINK_HREF))
            ),
            footnotes=_dedupe(footnotes),
            source_xml=etree.tostring(element, encoding="unicode", with_tail=False),
        )

    def _enclosing_section(self, element: etree._Element) -> str | None:
        """Return the ID of the nearest parsed section containing ``element``.

        Args:
            element: Any element inside body or back matter.

        Returns:
            The section ID, or None if none encloses it.
        """
        for ancestor in element.iterancestors():
            if ancestor in self._section_ids:
                return self._section_ids[ancestor]
        return None

    def _citing_section(self, xml_id: str | None) -> str | None:
        """Return the section of the first body or back ``xref`` citing an ID.

        Used for objects in ``floats-group``, which sit outside every section.

        Args:
            xml_id: The object's ``@id``, or None.

        Returns:
            The citing section's ID, or None if the object is not cited.
        """
        if xml_id is None:
            return None
        for container in (self._body, self._back):
            if container is None:
                continue
            for node in container.iter():
                # @rid may list several targets separated by spaces.
                if local_name(node) == "xref" and xml_id in (node.get("rid") or "").split():
                    return self._enclosing_section(node)
        return None

    # ----- conflicts of interest and funding ---------------------------

    def _coi_statements(self) -> tuple[str, ...]:
        """Collect conflict-of-interest statements as raw text.

        Sources: ``conflict`` elements; ``fn`` with a COI ``@fn-type``; and
        ``sec``, ``notes`` or ``fn-group`` elements whose type attribute or
        title names competing interests (Europe PMC, for example, moves the
        eLife COI footnote into a body section titled "Competing interests").

        Returns:
            Deduplicated statements in document order.
        """
        elements = _statement_elements(
            (self._meta, self._body, self._back),
            fn_types=_COI_FN_TYPES,
            title=_COI_TITLE,
            extra_names=frozenset({"conflict"}),
        )
        return _dedupe([flatten(e, skip=("label", "title")) for e in elements])

    def _funding(self) -> Funding:
        """Collect funding information as raw text.

        Returns:
            ``funding-group`` statements and award groups, plus funding
            footnotes and sections found in front, body or back matter.
        """
        statements: list[str] = []
        awards: list[FundingAward] = []
        for group in _children(self._meta, "funding-group"):
            for award in _children(group, "award-group"):
                awards.append(
                    FundingAward(
                        sources=_dedupe([flatten(s) for s in _children(award, "funding-source")]),
                        award_ids=_dedupe([flatten(a) for a in _children(award, "award-id")]),
                    )
                )
            statements.extend(flatten(s) for s in _children(group, "funding-statement"))
        # Funding also appears as footnotes and titled sections outside funding-group.
        elements = _statement_elements(
            (self._meta, self._body, self._back),
            fn_types=_FUNDING_TYPES,
            title=_FUNDING_TITLE,
            extra_names=frozenset(),
            exclude_names=frozenset({"funding-group"}),
        )
        statements.extend(flatten(e, skip=("label", "title")) for e in elements)
        return Funding(statements=_dedupe(statements), awards=tuple(awards))


def _statement_elements(
    containers: tuple[etree._Element | None, ...],
    *,
    fn_types: frozenset[str],
    title: re.Pattern[str],
    extra_names: frozenset[str],
    exclude_names: frozenset[str] = frozenset(),
) -> list[etree._Element]:
    """Find the elements holding a kind of statement (COI or funding).

    An element matches if it is named in ``extra_names``; if it is an ``fn``
    whose ``@fn-type`` is in ``fn_types``; or if it is a ``sec``, ``notes``
    or ``fn-group`` whose ``@sec-type``, ``@notes-type`` or ``@content-type``
    is in ``fn_types`` or whose ``title`` matches ``title``. Elements nested
    inside an earlier match are skipped so text is not collected twice.

    Args:
        containers: Elements to search (None entries are ignored).
        fn_types: Lower-case type values that mark a matching element.
        title: Pattern searched in the titles of candidate sections.
        extra_names: Local names that always match.
        exclude_names: Local names whose subtrees are never searched.

    Returns:
        Matching elements in document order.
    """
    matched: list[etree._Element] = []
    for container in containers:
        if container is None:
            continue
        for element in container.iter():
            name = local_name(element)
            # Skip anything nested inside an earlier match so its text is not collected twice.
            if not name or any(a in matched for a in element.iterancestors()):
                continue
            # Skip excluded subtrees (e.g. funding-group, which is read in structured form).
            if any(local_name(a) in exclude_names for a in element.iterancestors()):
                continue
            # Publishers put the statement type in different attributes; pool them.
            types = {
                (element.get(attr) or "").lower()
                for attr in ("fn-type", "sec-type", "notes-type", "content-type")
            }
            # Footnotes match on type alone; named elements such as <conflict> always match.
            if name in extra_names or (name == "fn" and types & fn_types):
                matched.append(element)
            # Section-like containers match on type, or on a title such as "Competing interests".
            elif name in {"sec", "notes", "fn-group"}:
                heading = _text(_child(element, "title"))
                if types & fn_types or (heading and title.search(heading)):
                    matched.append(element)
    return matched


def _blocks(
    element: etree._Element, name: str, kind: str | None = None
) -> list[tuple[etree._Element, str, str]]:
    """Turn one child of a section into paragraph blocks.

    Args:
        element: A child element of a section.
        name: Its local name.
        kind: Block kind to force (used inside boxed text), or None.

    Returns:
        ``(source element, kind, text)`` for each non-empty block. Figures,
        tables, reference lists and unknown elements yield nothing.
    """
    blocks: list[tuple[etree._Element, str, str]] = []
    if name in {"p", "verse-group"}:
        blocks.append((element, kind or "p", flatten(element)))
    elif name == "list":
        # One block per list item, so items align one-to-one in a rewrite.
        blocks.extend(
            (item, kind or "list-item", flatten(item)) for item in _children(element, "list-item")
        )
    elif name == "disp-quote":
        paragraphs = list(_children(element, "p"))
        if paragraphs:
            blocks.extend((p, kind or "quote", flatten(p)) for p in paragraphs)
        else:
            blocks.append((element, kind or "quote", flatten(element)))
    elif name == "def-list":
        for item in _children(element, "def-item"):
            term, definition = _text(_child(item, "term")), _text(_child(item, "def"))
            text = f"{term}: {definition}" if term and definition else (term or definition or "")
            blocks.append((item, kind or "def", text))
    elif name == "disp-formula":
        blocks.append((element, kind or "formula", flatten(element)))
    elif name in {"boxed-text", "statement"}:
        # Boxes may hold their own sections; their content is kept in place.
        box_kind = kind or ("boxed" if name == "boxed-text" else "p")
        for child in element:
            child_name = local_name(child)
            if child_name == "sec":
                for grandchild in child:
                    blocks.extend(_blocks(grandchild, local_name(grandchild), box_kind))
            else:
                blocks.extend(_blocks(child, child_name, box_kind))
    return [block for block in blocks if block[2]]


def _int(text: str | None) -> int | None:
    """Parse a decimal integer, returning None for missing or non-numeric text.

    Args:
        text: Text such as "2025" or "07".

    Returns:
        The integer, or None.
    """
    return int(text) if text and text.isdigit() else None


def _month(text: str | None) -> int | None:
    """Parse a month given as a number or an English name.

    Args:
        text: Text such as "4", "04", "Apr" or "April".

    Returns:
        The month 1-12, or None for missing, out-of-range or seasonal values.
    """
    if text is None:
        return None
    number = _int(text)
    if number is not None:
        return number if 1 <= number <= 12 else None
    return _MONTHS.get(text.strip().rstrip(".").lower())
