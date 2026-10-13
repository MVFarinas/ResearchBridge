"""Test support: a recorded PMC bucket and synthetic corpus builders.

Tests never use the network. :class:`RecordedBucket` serves the responses
recorded in ``tests/fixtures/pmc`` (and the verbatim eLife XML fixtures from
``libs/rbcore``) through ``httpx.MockTransport``; tests can add synthetic
responses, and every request is logged so tests can assert what was fetched.

Builders whose names start with ``synthetic_`` create rows that do not come
from any real source; they exist only to drive the gate into specific states.
Fixtures wrapping these live in ``conftest.py``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from rb_backend.corpus.blocks import evidence_row, rows_from_block
from rb_backend.corpus.models import (
    BlockScope,
    ContentState,
    Figure,
    LicenceRecord,
    Paper,
    PaperVersion,
    Paragraph,
    PermissionsBlockRecord,
    Section,
    Source,
)
from rb_backend.ingestion.pmc import BASE_URL
from rbcore.licences import LicenceEvidence, LicenceField, PermissionsBlock

TESTS = Path(__file__).parent
PMC_FIXTURES = TESTS / "fixtures" / "pmc"
RBCORE_JATS = TESTS.parent.parent / "libs" / "rbcore" / "tests" / "fixtures" / "jats"

# Verbatim XML fixtures by PMC version (MD5s match the recorded metadata).
RECORDED_XML: dict[str, Path] = {
    "PMC10718527.1": RBCORE_JATS / "elife-93719-pmc-s3.xml",
    "PMC7853715.1": RBCORE_JATS / "elife-65180-pmc-s3.xml",
    "PMC7781593.1": RBCORE_JATS / "elife-61907-pmc-s3.xml",
    "PMC11964404.1": PMC_FIXTURES / "PMC11964404.1.xml",
}
FIXED_NOW = datetime(2026, 10, 13, 12, 0, tzinfo=UTC)


@dataclass
class RecordedBucket:
    """A fake bucket host serving recorded (and optional synthetic) responses.

    Attributes:
        overrides: Extra responses by full URL (synthetic variations).
        requests: Every URL requested, in order.
    """

    overrides: dict[str, bytes] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Answer one request from overrides, then recorded files, else 404.

        Args:
            request: The request.

        Returns:
            The response.
        """
        url = str(request.url)
        self.requests.append(url)
        if url in self.overrides:
            return httpx.Response(200, content=self.overrides[url])
        # Overrides are stored normalised; compare the same way.
        normalised = _normalise(url)
        for key, override in self.overrides.items():
            if _normalise(key) == normalised:
                return httpx.Response(200, content=override)
        body = self._recorded(request.url)
        return httpx.Response(200, content=body) if body is not None else httpx.Response(404)

    def _recorded(self, url: httpx.URL) -> bytes | None:
        """Find the recorded file for a bucket URL.

        Args:
            url: The request URL.

        Returns:
            The file's bytes, or None.
        """
        path = url.path.strip("/")
        # Listings: ?list-type=2&prefix=PMC123.&delimiter=/
        if not path and url.params.get("list-type") == "2":
            pmcid = url.params["prefix"].rstrip(".")
            listing = PMC_FIXTURES / f"{pmcid}-listing.xml"
            return listing.read_bytes() if listing.is_file() else _empty_listing(pmcid)
        # Objects: <version>/<version>.json or .xml
        name = path.rsplit("/", 1)[-1]
        version_id, _, suffix = name.rpartition(".")
        if suffix == "json" and (PMC_FIXTURES / name).is_file():
            return (PMC_FIXTURES / name).read_bytes()
        if suffix == "xml" and version_id in RECORDED_XML:
            return RECORDED_XML[version_id].read_bytes()
        return None

    def add_metadata(self, metadata: dict[str, Any]) -> None:
        """Serve a (synthetic) metadata document at its bucket URL.

        Args:
            metadata: The JSON object; its pmcid and version give the URL.
        """
        version_id = f"{metadata['pmcid']}.{metadata['version']}"
        self.overrides[f"{BASE_URL}/{version_id}/{version_id}.json"] = json.dumps(metadata).encode()

    def add_listing(self, pmcid: str, versions: list[int]) -> None:
        """Serve a (synthetic) listing with the given version numbers.

        Args:
            pmcid: The PMC ID.
            versions: Version numbers to list.
        """
        prefixes = "".join(
            f"<CommonPrefixes><Prefix>{pmcid}.{n}/</Prefix></CommonPrefixes>" for n in versions
        )
        url = f"{BASE_URL}/?list-type=2&prefix={pmcid}.&delimiter=/"
        self.overrides[url] = _listing_xml(pmcid, prefixes)

    def add_xml(self, version_id: str, data: bytes) -> str:
        """Serve (synthetic) XML for a version and return its MD5.

        Args:
            version_id: e.g. ``PMC900000001.1``.
            data: The XML bytes.

        Returns:
            The MD5 hex digest to put in the metadata's ``xml_url``.
        """
        digest = hashlib.md5(data, usedforsecurity=False).hexdigest()
        self.overrides[f"{BASE_URL}/{version_id}/{version_id}.xml?md5={digest}"] = data
        return digest

    def fetched(self, suffix: str) -> list[str]:
        """Requested URLs whose path ends with ``suffix``.

        Args:
            suffix: e.g. ".xml".

        Returns:
            Matching URLs, in order.
        """
        return [url for url in self.requests if httpx.URL(url).path.endswith(suffix)]


def _normalise(url: str) -> tuple[str, str, tuple[tuple[str, str], ...]]:
    """Reduce a URL to host, path and sorted query parameters.

    Args:
        url: The URL.

    Returns:
        A comparable key that ignores percent-encoding differences.
    """
    parsed = httpx.URL(url)
    return parsed.host, parsed.path, tuple(sorted(parsed.params.multi_items()))


def _listing_xml(pmcid: str, prefixes: str) -> bytes:
    """Build a ListObjectsV2 document.

    Args:
        pmcid: The listed PMC ID.
        prefixes: ``CommonPrefixes`` elements.

    Returns:
        The XML bytes.
    """
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>pmc-oa-opendata</Name><Prefix>{pmcid}.</Prefix>"
        f"<IsTruncated>false</IsTruncated>{prefixes}</ListBucketResult>"
    ).encode()


def _empty_listing(pmcid: str) -> bytes:
    """A listing with no versions (the article is not in the bucket).

    Args:
        pmcid: The PMC ID.

    Returns:
        The XML bytes.
    """
    return _listing_xml(pmcid, "")


def recorded_metadata(version_id: str) -> dict[str, Any]:
    """Load a recorded metadata document as a dict (to derive synthetic variants).

    Args:
        version_id: e.g. ``PMC10718527.1``.

    Returns:
        The decoded JSON.
    """
    data: dict[str, Any] = json.loads((PMC_FIXTURES / f"{version_id}.json").read_bytes())
    return data


def synthetic_version(
    *,
    pmcid: str = "PMC900000001",
    version_number: int = 1,
    is_current: bool = True,
    content_state: ContentState = ContentState.PARSED,
    paper: Paper | None = None,
) -> PaperVersion:
    """Create a synthetic paper version with no licence records.

    Args:
        pmcid: A synthetic PMC ID (900000000+ never collides with real ones
            used in the fixtures).
        version_number: Version number.
        is_current: Whether it is current.
        content_state: Content state to record.
        paper: An existing paper to attach to.

    Returns:
        The saved version.
    """
    paper = paper or Paper.objects.create(pmcid=pmcid)
    return PaperVersion.objects.create(
        paper=paper,
        source=Source.PMC,
        source_version_id=f"{paper.pmcid}.{version_number}",
        version_number=version_number,
        is_current=is_current,
        title="Synthetic test paper (not a real article)",
        metadata_url=f"{BASE_URL}/{paper.pmcid}.{version_number}/{paper.pmcid}.{version_number}.json",
        content_state=content_state,
    )


def synthetic_code(
    version: PaperVersion, code: str, field: LicenceField = LicenceField.PMC_LICENSE_CODE
) -> LicenceRecord:
    """Attach a synthetic non-JATS licence value to a version.

    Args:
        version: The version.
        code: The raw value.
        field: The source field.

    Returns:
        The saved record.
    """
    record = evidence_row(
        version,
        LicenceEvidence(field, code),
        position=version.licence_records.count(),
        source_url=version.metadata_url,
        retrieved_at=FIXED_NOW,
    )
    record.save()
    return record


def synthetic_block(
    version: PaperVersion,
    block: PermissionsBlock,
    *,
    scope: BlockScope,
    figure: Figure | None = None,
    paragraph: Paragraph | None = None,
    position: int = 0,
) -> PermissionsBlockRecord:
    """Attach a synthetic JATS permissions block to a version or one of its parts.

    Args:
        version: The version.
        block: The block.
        scope: Article, figure, paragraph or unattached.
        figure: The figure (figure scope).
        paragraph: The paragraph (paragraph scope).
        position: Order among the part's blocks.

    Returns:
        The saved block row.
    """
    part = figure or paragraph
    rows = rows_from_block(
        version,
        block,
        scope=scope,
        position=position,
        source_url=f"{BASE_URL}/{version.source_version_id}/{version.source_version_id}.xml",
        retrieved_at=FIXED_NOW,
        figure=figure,
        paragraph=paragraph,
        part_stable_id=part.stable_id if part is not None else "",
    )
    rows.block.save()
    for record in rows.records:
        record.block = rows.block
        record.save()
    return rows.block


def synthetic_content(version: PaperVersion, *, paragraphs: int = 2, figures: int = 1) -> None:
    """Give a version a synthetic body section, paragraphs and figures.

    Args:
        version: The version.
        paragraphs: How many paragraphs.
        figures: How many figures.
    """
    section = Section.objects.create(version=version, stable_id="body", kind="body", position=0)
    for i in range(paragraphs):
        text = f"Synthetic paragraph {i + 1} about mitochondria (not real text)."
        Paragraph.objects.create(
            version=version,
            section=section,
            stable_id=f"body-p{i + 1}",
            kind="p",
            text=text,
            text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            position=i,
        )
    for i in range(figures):
        Figure.objects.create(
            version=version,
            stable_id=f"fig{i + 1}",
            kind=Figure.Kind.FIGURE,
            label=f"Synthetic figure {i + 1}",
            position=i,
        )
