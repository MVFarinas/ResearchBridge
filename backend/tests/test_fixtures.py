"""The recorded fixtures are byte-for-byte what the manifest says."""

from __future__ import annotations

import hashlib
import json

import pytest
from support import PMC_FIXTURES, RECORDED_XML

from rb_backend.ingestion.pmc import PmcMetadata

MANIFEST = json.loads((PMC_FIXTURES / "manifest.json").read_text())


@pytest.mark.parametrize("entry", MANIFEST["fixtures"], ids=lambda e: e["file"])
def test_fixture_matches_manifest_checksum(entry: dict[str, str]) -> None:
    """Every recorded file still has the SHA-256 recorded at download time."""
    data = (PMC_FIXTURES / entry["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_every_fixture_file_is_in_the_manifest() -> None:
    """No unlisted (and so unattributed) file sneaks into the fixture directory."""
    listed = {entry["file"] for entry in MANIFEST["fixtures"]}
    present = {p.name for p in PMC_FIXTURES.iterdir() if p.suffix in {".xml", ".json"}}
    assert present - {"manifest.json"} == listed


@pytest.mark.parametrize("version_id", sorted(RECORDED_XML))
def test_reused_xml_matches_the_md5_in_recorded_metadata(version_id: str) -> None:
    """The XML files served for each version are exactly the bucket's objects."""
    metadata = PmcMetadata.from_json((PMC_FIXTURES / f"{version_id}.json").read_bytes())
    data = RECORDED_XML[version_id].read_bytes()
    assert hashlib.md5(data, usedforsecurity=False).hexdigest() == metadata.xml_md5
