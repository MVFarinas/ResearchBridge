"""Write parsed articles and licence provenance into the corpus tables.

Content is upserted by rbcore's stable IDs, so re-ingesting an unchanged
article changes nothing, and re-ingesting a changed one keeps the primary
keys of paragraphs that still exist (annotations stay attached). Licence
records are never edited: a value that is still the same is re-confirmed, a
changed one supersedes the old record.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from rb_backend.corpus.blocks import evidence_row, rows_from_block
from rb_backend.corpus.models import (
    BlockScope,
    Figure,
    LicenceRecord,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
    Section,
)
from rb_backend.corpus.retention import delete_parts, supersede_blocks
from rbcore.jats import Article
from rbcore.jats import Figure as JatsFigure
from rbcore.jats import Section as JatsSection
from rbcore.licences import LicenceEvidence, LicenceField

# Section fields copied from the parsed article on every upsert.
_SECTION_FIELDS = ("parent", "kind", "title", "label", "sec_type", "xml_id", "position")
_PARAGRAPH_FIELDS = (
    "section",
    "kind",
    "text",
    "text_sha256",
    "source_xml",
    "position",
    "has_own_permissions",
)
_FIGURE_FIELDS = (
    "kind",
    "label",
    "caption_title",
    "caption",
    "section_stable_id",
    "xml_id",
    "graphics",
    "footnotes",
    "source_xml",
    "position",
    "has_own_permissions",
)


@dataclass(frozen=True, slots=True)
class _FlatSection:
    """One parsed section with its place in the tree.

    Attributes:
        section: The parsed section.
        parent_id: Stable ID of its parent, or None for a root.
        depth: 0 for roots.
    """

    section: JatsSection
    parent_id: str | None
    depth: int


def sync_source_records(
    version: PaperVersion,
    fields: Sequence[LicenceField],
    evidence: Sequence[LicenceEvidence],
    *,
    source_url: str,
    retrieved_at: datetime,
) -> bool:
    """Bring a version's non-JATS licence records for some fields up to date.

    Args:
        version: The version.
        fields: The fields this source owns (e.g. the PMC licence code).
        evidence: The values found now, in source order.
        source_url: The document they were read from.
        retrieved_at: When it was read.

    Returns:
        True if the records changed (old ones superseded, new ones written);
        False if the same values were re-confirmed.
    """
    active = list(
        LicenceRecord.objects.active()
        .filter(version=version, block__isnull=True, field__in=[f.value for f in fields])
        .order_by("position", "pk")
    )
    # Same values in the same order: only refresh the confirmation time.
    if [record.as_evidence() for record in active] == list(evidence):
        LicenceRecord.objects.filter(pk__in=[r.pk for r in active]).update(
            last_confirmed_at=retrieved_at
        )
        return False

    LicenceRecord.objects.filter(pk__in=[r.pk for r in active]).update(superseded_at=retrieved_at)
    LicenceRecord.objects.bulk_create(
        evidence_row(version, item, position=i, source_url=source_url, retrieved_at=retrieved_at)
        for i, item in enumerate(evidence)
    )
    return True


def store_article(
    version: PaperVersion, article: Article, *, source_url: str, retrieved_at: datetime
) -> None:
    """Store a parsed article's metadata, content and permissions blocks.

    Args:
        version: The version (saved by the caller afterwards for metadata).
        article: The parsed JATS article.
        source_url: URL of the XML.
        retrieved_at: When the XML was retrieved.
    """
    _apply_metadata(version, article)
    sections = _upsert_sections(version, article, retrieved_at)
    paragraphs = _upsert_paragraphs(version, article, sections, retrieved_at)
    figures = _upsert_figures(version, article, retrieved_at)
    _replace_blocks(
        version,
        article,
        paragraphs,
        figures,
        source_url=source_url,
        retrieved_at=retrieved_at,
    )


def _apply_metadata(version: PaperVersion, article: Article) -> None:
    """Copy bibliographic metadata from the parsed article onto the version.

    Args:
        version: The version.
        article: The parsed article.
    """
    published = article.published
    version.title = article.title or version.title
    version.journal_title = article.journal.title or ""
    version.journal_nlm_ta = article.journal.nlm_ta or ""
    version.journal_issns = list(article.journal.issns)
    version.publisher = article.journal.publisher or ""
    version.article_type = article.article_type or ""
    version.subject_heading = article.subject_heading or ""
    version.language = article.language or ""
    version.published_date = (published.iso if published else None) or ""
    version.authors = [
        {
            "name": author.display_name,
            "surname": author.surname,
            "given_names": author.given_names,
            "collab": author.collab,
            "orcid": author.orcid,
            "corresponding": author.corresponding,
        }
        for author in article.authors
    ]
    version.coi_statements = list(article.coi_statements)
    version.funding = {
        "statements": list(article.funding.statements),
        "awards": [
            {"sources": list(award.sources), "award_ids": list(award.award_ids)}
            for award in article.funding.awards
        ],
    }


def _flatten(roots: Sequence[JatsSection]) -> Iterator[_FlatSection]:
    """Yield every section depth first, with its parent ID and depth.

    Args:
        roots: Root sections (abstracts, body, back).

    Yields:
        Sections in document order.
    """
    stack: list[tuple[JatsSection, str | None, int]] = [(root, None, 0) for root in reversed(roots)]
    while stack:
        section, parent_id, depth = stack.pop()
        yield _FlatSection(section, parent_id, depth)
        stack.extend((child, section.id, depth + 1) for child in reversed(section.sections))


def _roots(article: Article) -> list[JatsSection]:
    """The article's root sections in document order.

    Args:
        article: The parsed article.

    Returns:
        Abstracts, then body, then back matter.
    """
    return [*article.abstracts, article.body, article.back]


def _upsert_sections(version: PaperVersion, article: Article, when: datetime) -> dict[str, Section]:
    """Create, update and delete sections to match the parsed article.

    Args:
        version: The version.
        article: The parsed article.
        when: Time to record on reviews of deleted paragraphs.

    Returns:
        Section rows by stable ID.
    """
    existing = {s.stable_id: s for s in Section.objects.filter(version=version)}
    flat = list(_flatten(_roots(article)))
    by_id: dict[str, Section] = {}

    # Parents must exist before children, so work one depth level at a time.
    for depth in sorted({item.depth for item in flat}):
        created: list[Section] = []
        updated: list[Section] = []
        for position, item in enumerate(flat):
            if item.depth != depth:
                continue
            values = _section_values(item, position, by_id)
            row = existing.get(item.section.id)
            if row is None:
                row = Section(version=version, stable_id=item.section.id, **values)
                created.append(row)
            else:
                for name, value in values.items():
                    setattr(row, name, value)
                updated.append(row)
            by_id[item.section.id] = row
        Section.objects.bulk_create(created)
        Section.objects.bulk_update(updated, list(_SECTION_FIELDS))

    # Sections that no longer exist go last, after nothing points at them.
    stale = set(existing) - set(by_id)
    if stale:
        delete_parts(
            paragraphs=Paragraph.objects.filter(version=version, section__stable_id__in=stale),
            when=when,
        )
        Section.objects.filter(version=version, stable_id__in=stale).delete()
    return by_id


def _section_values(item: _FlatSection, position: int, by_id: dict[str, Section]) -> dict[str, Any]:
    """Field values for one section row.

    Args:
        item: The flattened section.
        position: Its document position.
        by_id: Rows already upserted (contains the parent).

    Returns:
        Values for :data:`_SECTION_FIELDS`.
    """
    section = item.section
    return {
        "parent": by_id[item.parent_id] if item.parent_id else None,
        "kind": section.kind,
        "title": section.title or "",
        "label": section.label or "",
        "sec_type": section.sec_type or "",
        "xml_id": section.xml_id or "",
        "position": position,
    }


def _upsert_paragraphs(
    version: PaperVersion, article: Article, sections: dict[str, Section], when: datetime
) -> dict[str, Paragraph]:
    """Create, update and delete paragraphs to match the parsed article.

    Args:
        version: The version.
        article: The parsed article.
        sections: Section rows by stable ID.
        when: Time to record on reviews of deleted paragraphs.

    Returns:
        Paragraph rows by stable ID.
    """
    existing = {p.stable_id: p for p in Paragraph.objects.filter(version=version)}
    created: list[Paragraph] = []
    updated: list[Paragraph] = []
    by_id: dict[str, Paragraph] = {}
    position = 0

    for item in _flatten(_roots(article)):
        for parsed in item.section.paragraphs:
            values = {
                "section": sections[item.section.id],
                "kind": parsed.kind,
                "text": parsed.text,
                "text_sha256": hashlib.sha256(parsed.text.encode("utf-8")).hexdigest(),
                "source_xml": parsed.source_xml,
                "position": position,
                "has_own_permissions": bool(parsed.permissions),
            }
            position += 1
            row = existing.get(parsed.id)
            if row is None:
                row = Paragraph(version=version, stable_id=parsed.id, **values)
                created.append(row)
            else:
                for name, value in values.items():
                    setattr(row, name, value)
                updated.append(row)
            by_id[parsed.id] = row

    Paragraph.objects.bulk_create(created, batch_size=500)
    Paragraph.objects.bulk_update(updated, list(_PARAGRAPH_FIELDS), batch_size=500)
    delete_parts(
        paragraphs=Paragraph.objects.filter(version=version).exclude(stable_id__in=list(by_id)),
        when=when,
    )
    return by_id


def _upsert_figures(version: PaperVersion, article: Article, when: datetime) -> dict[str, Figure]:
    """Create, update and delete figures and tables to match the parsed article.

    Args:
        version: The version.
        article: The parsed article.
        when: Time to record on reviews of deleted figures.

    Returns:
        Figure rows by stable ID.
    """
    existing = {f.stable_id: f for f in Figure.objects.filter(version=version)}
    created: list[Figure] = []
    updated: list[Figure] = []
    by_id: dict[str, Figure] = {}

    for position, parsed in enumerate((*article.figures, *article.tables)):
        values = _figure_values(parsed, position)
        row = existing.get(parsed.id)
        if row is None:
            row = Figure(version=version, stable_id=parsed.id, **values)
            created.append(row)
        else:
            for name, value in values.items():
                setattr(row, name, value)
            updated.append(row)
        by_id[parsed.id] = row

    Figure.objects.bulk_create(created)
    Figure.objects.bulk_update(updated, list(_FIGURE_FIELDS))
    delete_parts(
        figures=Figure.objects.filter(version=version).exclude(stable_id__in=list(by_id)),
        when=when,
    )
    return by_id


def _figure_values(parsed: JatsFigure, position: int) -> dict[str, Any]:
    """Field values for one figure or table row.

    Args:
        parsed: The parsed figure or table.
        position: Its position among the version's figures and tables.

    Returns:
        Values for :data:`_FIGURE_FIELDS`.
    """
    return {
        "kind": Figure.Kind.TABLE if parsed.kind == "table" else Figure.Kind.FIGURE,
        "label": parsed.label or "",
        "caption_title": parsed.caption_title or "",
        "caption": parsed.caption,
        "section_stable_id": parsed.section_id or "",
        "xml_id": parsed.xml_id or "",
        "graphics": list(parsed.graphics),
        "footnotes": list(parsed.footnotes),
        "source_xml": parsed.source_xml,
        "position": position,
        "has_own_permissions": bool(parsed.permissions),
    }


def _replace_blocks(
    version: PaperVersion,
    article: Article,
    paragraphs: dict[str, Paragraph],
    figures: dict[str, Figure],
    *,
    source_url: str,
    retrieved_at: datetime,
) -> None:
    """Supersede the old JATS permissions blocks and store the new ones.

    Args:
        version: The version.
        article: The parsed article.
        paragraphs: Paragraph rows by stable ID.
        figures: Figure rows by stable ID.
        source_url: URL of the XML.
        retrieved_at: When it was retrieved.
    """
    supersede_blocks(version, retrieved_at)
    built = []

    # Article-level block (at most one) and blocks the parser could not attach.
    if article.permissions is not None:
        built.append(
            rows_from_block(
                version,
                article.permissions,
                scope=BlockScope.ARTICLE,
                position=0,
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
        )
    built.extend(
        rows_from_block(
            version,
            block,
            scope=BlockScope.UNATTACHED,
            position=i,
            source_url=source_url,
            retrieved_at=retrieved_at,
        )
        for i, block in enumerate(article.unattached_permissions)
    )

    # Part-level blocks: figure/table overrides and paragraph-level permissions.
    for parsed_figure in (*article.figures, *article.tables):
        built.extend(
            rows_from_block(
                version,
                block,
                scope=BlockScope.FIGURE,
                position=i,
                figure=figures[parsed_figure.id],
                part_stable_id=parsed_figure.id,
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
            for i, block in enumerate(parsed_figure.permissions)
        )
    for root in _roots(article):
        for parsed_paragraph in root.iter_paragraphs():
            built.extend(
                rows_from_block(
                    version,
                    block,
                    scope=BlockScope.PARAGRAPH,
                    position=i,
                    paragraph=paragraphs[parsed_paragraph.id],
                    part_stable_id=parsed_paragraph.id,
                    source_url=source_url,
                    retrieved_at=retrieved_at,
                )
                for i, block in enumerate(parsed_paragraph.permissions)
            )

    # Blocks first (to get primary keys), then their records.
    PermissionsBlockRecord.objects.bulk_create([rows.block for rows in built])
    LicenceRecord.objects.bulk_create([record for rows in built for record in rows.records])
