"""Permissions blocks survive the trip into database rows and back exactly."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from support import PMC_FIXTURES, RBCORE_JATS

from rb_backend.corpus.blocks import block_from_rows, evidence_summary, rows_from_block
from rb_backend.corpus.models import BlockScope, PaperVersion
from rbcore.jats import parse_jats_file
from rbcore.licences import (
    AliLicenceRef,
    LicenceField,
    LicenceStatement,
    PermissionsBlock,
)

XML_FILES = [*sorted(RBCORE_JATS.glob("*.xml")), PMC_FIXTURES / "PMC11964404.1.xml"]
NOW = datetime(2026, 10, 13, tzinfo=UTC)


def all_blocks(path: Path) -> Iterator[PermissionsBlock]:
    """Every permissions block of a real article: article, parts and unattached."""
    article = parse_jats_file(path)
    if article.permissions is not None:
        yield article.permissions
    yield from article.unattached_permissions
    for figure in (*article.figures, *article.tables):
        yield from figure.permissions
    for root in (*article.abstracts, article.body, article.back):
        for paragraph in root.iter_paragraphs():
            yield from paragraph.permissions


def round_trip(block: PermissionsBlock) -> PermissionsBlock:
    """Store a block as unsaved rows and rebuild it."""
    rows = rows_from_block(
        PaperVersion(source_version_id="PMC0.1"),
        block,
        scope=BlockScope.ARTICLE,
        position=0,
        source_url="https://example.invalid/synthetic.xml",
        retrieved_at=NOW,
    )
    return block_from_rows(rows.block, rows.records)


@pytest.mark.parametrize("path", XML_FILES, ids=lambda p: p.name)
def test_real_blocks_round_trip_exactly(path: Path) -> None:
    """Every block in every real fixture rebuilds to an equal rbcore value."""
    blocks = list(all_blocks(path))
    assert blocks, "each fixture has at least an article-level block"
    for block in blocks:
        assert round_trip(block) == block


def test_synthetic_block_with_every_field_round_trips() -> None:
    """Dates, scopes, empty statements, prose and inner flags all survive."""
    # A synthetic block that sets every field rbcore models, including edge cases.
    block = PermissionsBlock(
        copyright_statement="(c) Synthetic Holder",
        copyright_years=("2020",),
        copyright_holders=("Synthetic Holder",),
        licences=(
            LicenceStatement(
                xlink_href="https://creativecommons.org/licenses/by/4.0/",
                ali_license_refs=(
                    AliLicenceRef(
                        "https://creativecommons.org/licenses/by-nc/4.0/", "vor", "2020-01-01"
                    ),
                    AliLicenceRef(
                        "https://creativecommons.org/licenses/by/4.0/",
                        "textmining",
                        "2021-01-01",
                        "2030-01-01",
                    ),
                ),
                license_type="open-access",
                prose="Synthetic licence prose.",
            ),
            LicenceStatement(),
        ),
        free_to_read=True,
        free_to_read_start_date="2020-01-01",
        context="graphic",
        inner=True,
    )

    # Storing and rebuilding it loses nothing.
    assert round_trip(block) == block


def test_records_keep_raw_value_field_and_normalisation() -> None:
    """Each record holds the raw value, its field, and rbcore's normalisation."""
    # A synthetic block with a ported CC licence URI and some prose.
    block = PermissionsBlock(
        licences=(
            LicenceStatement(
                ali_license_refs=(
                    AliLicenceRef("http://creativecommons.org/licenses/by-sa/3.0/igo/"),
                ),
                prose="Synthetic prose.",
            ),
        )
    )

    # Act: build the rows that would be stored for it.
    rows = rows_from_block(
        PaperVersion(source_version_id="PMC0.1"),
        block,
        scope=BlockScope.ARTICLE,
        position=0,
        source_url="https://example.invalid/synthetic.xml",
        retrieved_at=NOW,
    )

    # Each record keeps its source field and rbcore's normalisation of the raw value.
    ali, prose = rows.records
    assert (
        ali.field,
        ali.normalised_family,
        ali.normalised_version,
        ali.normalised_jurisdiction,
    ) == (
        LicenceField.JATS_ALI_LICENSE_REF.value,
        "cc-by-sa",
        "3.0",
        "igo",
    )
    assert (prose.field, prose.normalised_family) == (LicenceField.JATS_LICENSE_P.value, "unknown")

    # Provenance: where and when the value was read.
    assert ali.source_url == "https://example.invalid/synthetic.xml"
    assert ali.retrieved_at == NOW == ali.last_confirmed_at


def test_evidence_summary_is_json_ready() -> None:
    """The reviewer's snapshot lists context, holders and each value."""
    # A synthetic figure block with only licence prose.
    block = PermissionsBlock(
        copyright_holders=("Synthetic Holder",),
        licences=(LicenceStatement(prose="Not covered by the CC BY licence (synthetic)."),),
        context="fig",
    )

    # The summary names the context, holders and each value with its field.
    summary = evidence_summary(block)
    assert summary["context"] == "fig"
    assert summary["copyright_holders"] == ["Synthetic Holder"]
    assert summary["evidence"] == [
        {
            "field": "jats:license-p",
            "value": "Not covered by the CC BY licence (synthetic).",
            "specific_use": None,
            "start_date": None,
            "end_date": None,
        }
    ]
