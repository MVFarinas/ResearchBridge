"""Convert JATS permissions blocks between rbcore values and database rows.

The round trip is exact: :func:`block_from_rows` rebuilds the same
:class:`rbcore.licences.PermissionsBlock` that :func:`rows_from_block` stored,
so the gate can be recomputed from the database alone. A test checks this on
every block of the real fixtures.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from rb_backend.corpus.models import (
    BlockScope,
    Figure,
    LicenceRecord,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
)
from rbcore.licences import (
    AliLicenceRef,
    LicenceEvidence,
    LicenceField,
    LicenceStatement,
    PermissionsBlock,
    normalise_licence,
)


@dataclass(frozen=True, slots=True)
class BlockRows:
    """Unsaved rows for one permissions block.

    Attributes:
        block: The block row.
        records: Its licence records, in statement and evidence order. Their
            ``block`` is set to ``block`` and must be saved after it.
    """

    block: PermissionsBlockRecord
    records: tuple[LicenceRecord, ...]


def evidence_row(
    version: PaperVersion,
    item: LicenceEvidence,
    *,
    position: int,
    source_url: str,
    retrieved_at: datetime,
    block: PermissionsBlockRecord | None = None,
    statement_index: int | None = None,
) -> LicenceRecord:
    """Build an unsaved licence record for one piece of evidence.

    Machine-readable values are normalised so the record shows what the
    gate would read; prose is stored with family "unknown".

    Args:
        version: The paper version.
        item: The evidence.
        position: Order within its statement or source document.
        source_url: The document it was read from.
        retrieved_at: When it was retrieved.
        block: The JATS block, for JATS fields.
        statement_index: The ``<license>`` index, for JATS fields.

    Returns:
        The unsaved record.
    """
    licence = normalise_licence(item.value) if item.field.is_machine_readable else None
    return LicenceRecord(
        version=version,
        block=block,
        statement_index=statement_index,
        position=position,
        field=item.field.value,
        raw_value=item.value,
        normalised_family=licence.family.value if licence else "unknown",
        normalised_version=(licence.version or "") if licence else "",
        normalised_jurisdiction=(licence.jurisdiction or "") if licence else "",
        specific_use=item.specific_use or "",
        start_date=item.start_date or "",
        end_date=item.end_date or "",
        source_url=source_url,
        retrieved_at=retrieved_at,
        last_confirmed_at=retrieved_at,
    )


def rows_from_block(
    version: PaperVersion,
    block: PermissionsBlock,
    *,
    scope: BlockScope,
    position: int,
    source_url: str,
    retrieved_at: datetime,
    figure: Figure | None = None,
    paragraph: Paragraph | None = None,
    part_stable_id: str = "",
) -> BlockRows:
    """Build unsaved rows for one rbcore permissions block.

    Args:
        version: The paper version.
        block: The parsed block.
        scope: What the block applies to.
        position: Order among the part's blocks.
        source_url: The XML it was read from.
        retrieved_at: When that XML was retrieved.
        figure: The figure (figure scope).
        paragraph: The paragraph (paragraph scope).
        part_stable_id: The part's stable ID ("" for article scope).

    Returns:
        The block row and its records.
    """
    row = PermissionsBlockRecord(
        version=version,
        scope=scope,
        figure=figure,
        paragraph=paragraph,
        part_stable_id=part_stable_id,
        position=position,
        context=block.context or "",
        inner=block.inner,
        statement_count=len(block.licences),
        copyright_statement=block.copyright_statement or "",
        copyright_years=list(block.copyright_years),
        copyright_holders=list(block.copyright_holders),
        free_to_read=block.free_to_read,
        free_to_read_start_date=block.free_to_read_start_date or "",
        free_to_read_end_date=block.free_to_read_end_date or "",
        source_url=source_url,
        retrieved_at=retrieved_at,
    )
    # One record per evidence item, numbered within its <license> statement.
    records = tuple(
        evidence_row(
            version,
            item,
            position=position_in_statement,
            source_url=source_url,
            retrieved_at=retrieved_at,
            block=row,
            statement_index=statement_index,
        )
        for statement_index, statement in enumerate(block.licences)
        for position_in_statement, item in enumerate(statement.evidence())
    )
    return BlockRows(row, records)


def block_from_rows(
    row: PermissionsBlockRecord, records: Sequence[LicenceRecord]
) -> PermissionsBlock:
    """Rebuild the rbcore permissions block that :func:`rows_from_block` stored.

    Args:
        row: The block row.
        records: All of its licence records (any order).

    Returns:
        The block, equal to the one originally parsed.
    """
    # Group the records back into their <license> statements, in evidence order.
    by_statement: dict[int, list[LicenceRecord]] = defaultdict(list)
    for record in sorted(records, key=lambda r: (r.statement_index or 0, r.position)):
        by_statement[record.statement_index or 0].append(record)

    statements = tuple(
        _statement(by_statement.get(index, [])) for index in range(row.statement_count)
    )
    return PermissionsBlock(
        copyright_statement=row.copyright_statement or None,
        copyright_years=tuple(row.copyright_years),
        copyright_holders=tuple(row.copyright_holders),
        licences=statements,
        free_to_read=row.free_to_read,
        free_to_read_start_date=row.free_to_read_start_date or None,
        free_to_read_end_date=row.free_to_read_end_date or None,
        context=row.context or None,
        inner=row.inner,
    )


def _statement(records: Sequence[LicenceRecord]) -> LicenceStatement:
    """Rebuild one ``<license>`` statement from its records.

    Args:
        records: The statement's records in evidence order.

    Returns:
        The statement.
    """
    refs: list[AliLicenceRef] = []
    xlink_href: str | None = None
    license_type: str | None = None
    prose: str | None = None
    # Each JATS field maps back to one attribute of the statement.
    for record in records:
        field = record.licence_field
        if field is LicenceField.JATS_ALI_LICENSE_REF:
            refs.append(
                AliLicenceRef(
                    value=record.raw_value,
                    specific_use=record.specific_use or None,
                    start_date=record.start_date or None,
                    end_date=record.end_date or None,
                )
            )
        elif field is LicenceField.JATS_LICENSE_XLINK_HREF:
            xlink_href = record.raw_value
        elif field is LicenceField.JATS_LICENSE_TYPE:
            license_type = record.raw_value
        elif field is LicenceField.JATS_LICENSE_P:
            prose = record.raw_value
    return LicenceStatement(
        xlink_href=xlink_href,
        ali_license_refs=tuple(refs),
        license_type=license_type,
        prose=prose,
    )


def evidence_summary(block: PermissionsBlock) -> dict[str, object]:
    """Summarise a block for a reviewer: context, copyright and licence values.

    Args:
        block: The block.

    Returns:
        A JSON-serialisable dictionary.
    """
    return {
        "context": block.context,
        "inner": block.inner,
        "copyright_statement": block.copyright_statement,
        "copyright_holders": list(block.copyright_holders),
        "evidence": [evidence_dict(item) for item in block.evidence()],
    }


def evidence_dict(item: LicenceEvidence) -> dict[str, str | None]:
    """Serialise one piece of evidence for a review snapshot.

    Args:
        item: The evidence.

    Returns:
        A JSON-serialisable dictionary.
    """
    return {
        "field": item.field.value,
        "value": item.value,
        "specific_use": item.specific_use,
        "start_date": item.start_date,
        "end_date": item.end_date,
    }
