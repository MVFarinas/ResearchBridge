"""The recorded metadata fixtures are what the manifest says, and all attributed."""

from __future__ import annotations

import hashlib

import pytest
from metadata_support import MANIFEST, METADATA_FIXTURES


@pytest.mark.parametrize("entry", MANIFEST["fixtures"], ids=lambda e: e["file"])
def test_fixture_matches_manifest_checksum(entry: dict[str, str]) -> None:
    """Every recorded file still has the SHA-256 recorded at download time."""
    data = (METADATA_FIXTURES / entry["file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"]


def test_every_fixture_file_is_in_the_manifest() -> None:
    """No unlisted (and so unattributed) file sneaks into the fixture directory."""
    listed = {entry["file"] for entry in MANIFEST["fixtures"]}
    present = {p.name for p in METADATA_FIXTURES.glob("*.json")}
    assert present - {"manifest.json"} == listed


def test_no_fixture_contains_an_api_key_or_email() -> None:
    """Requests were recorded without keys or personal identifiers."""
    for entry in MANIFEST["fixtures"]:
        assert "api_key" not in entry["source_url"]
        assert "mailto" not in entry["source_url"]
        assert "email=" not in entry["source_url"]
