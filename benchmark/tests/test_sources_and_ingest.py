"""Tests of the PMC Cloud Service client, safe XML parsing and ingest.

Ingest runs on the real CC BY fixtures committed in Phase 0
(libs/rbcore/tests/fixtures/jats, attribution in their README). PMC
responses are SYNTHETIC, served by httpx.MockTransport.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from rbbench.ingest import (
    EvidenceRecord,
    PaperSource,
    ingest_paper,
    load_passages,
    load_units,
    passage_units,
    write_ingest,
)
from rbbench.paths import RBCORE_FIXTURES_DIR
from rbbench.sources import pmc
from rbbench.sources.papers import fixture_sources
from rbbench.sources.safexml import UnsafeXmlError, parse_untrusted_xml
from rbcore.http import PoliteFetcher, RateLimiter


def _fetcher(handler: httpx.MockTransport, tmp_path: Path) -> PoliteFetcher:
    """A non-sleeping fetcher over a mock transport."""
    return PoliteFetcher(
        cache_dir=tmp_path / "cache",
        transport=handler,
        rate_limiter=RateLimiter(sleep=lambda _s: None),
        sleep=lambda _s: None,
    )


def test_s3_to_https_and_record_parsing() -> None:
    """Object URLs convert to HTTPS with their MD5; records keep every flag."""
    url, md5 = pmc.s3_to_https("s3://pmc-oa-opendata/PMC9.2/PMC9.2.xml?md5=abc")
    assert (url, md5) == ("https://pmc-oa-opendata.s3.amazonaws.com/PMC9.2/PMC9.2.xml", "abc")
    with pytest.raises(pmc.PmcError):
        pmc.s3_to_https("s3://another-bucket/x.xml")
    data = json.dumps(
        {
            "pmcid": "PMC9",
            "version": 2,
            "license_code": "TDM",
            "is_manuscript": True,
            "xml_url": "s3://pmc-oa-opendata/PMC9.2/PMC9.2.xml",
        }
    ).encode()
    record = pmc.parse_record(data, "u")
    assert (record.key, record.license_code, record.is_manuscript) == ("PMC9.2", "TDM", True)
    assert record.xml_md5 is None
    with pytest.raises(pmc.PmcError):
        pmc.parse_record(b"[]", "u")


def test_latest_version_and_md5_check(tmp_path: Path) -> None:
    """The newest listed version wins; a JATS whose MD5 differs is refused."""
    listing = (
        b'<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><CommonPrefixes>'
        b"<Prefix>PMC7.1/</Prefix></CommonPrefixes><CommonPrefixes><Prefix>PMC7.3/</Prefix>"
        b"</CommonPrefixes><CommonPrefixes><Prefix>PMC77.9/</Prefix></CommonPrefixes>"
        b"</ListBucketResult>"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        """Serve a listing and a JATS body."""
        if "list-type" in str(request.url):
            return httpx.Response(200, content=listing)
        return httpx.Response(200, content=b"<article/>")

    with _fetcher(httpx.MockTransport(handler), tmp_path) as fetcher:
        assert pmc.latest_version(fetcher, "PMC7") == 3
        good = hashlib.md5(b"<article/>", usedforsecurity=False).hexdigest()
        record = pmc.parse_record(
            json.dumps(
                {"pmcid": "PMC7", "xml_url": f"s3://pmc-oa-opendata/a.xml?md5={good}"}
            ).encode(),
            "u",
        )
        assert pmc.fetch_jats(fetcher, record) == b"<article/>"
        bad = pmc.parse_record(
            json.dumps({"pmcid": "PMC7", "xml_url": "s3://pmc-oa-opendata/b.xml?md5=00"}).encode(),
            "u",
        )
        with pytest.raises(pmc.PmcError, match="MD5"):
            pmc.fetch_jats(fetcher, bad)


def test_safe_xml_refuses_doctype_and_entities() -> None:
    """XML with a DOCTYPE (the vehicle for XXE and entity bombs) is refused."""
    xxe = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>'
    with pytest.raises(UnsafeXmlError):
        parse_untrusted_xml(xxe)
    with pytest.raises(UnsafeXmlError, match="malformed"):
        parse_untrusted_xml(b"<r>")
    with pytest.raises(UnsafeXmlError, match="exceeds"):
        parse_untrusted_xml(b"<r/>", max_bytes=2)
    assert parse_untrusted_xml(b"<r><a/></r>").tag == "r"


def test_ingest_fixture_gives_stable_unit_ids_and_a_passage() -> None:
    """A CC BY fixture yields units keyed by paper and paragraph ID, plus a passage."""
    source = next(s for s in fixture_sources(RBCORE_FIXTURES_DIR) if "65180" in s.paper_key)
    paper = ingest_paper(source)
    again = ingest_paper(source)
    assert paper.usable
    assert paper.licence == "CC BY"
    assert [u.unit_id for u in paper.units] == [u.unit_id for u in again.units]
    assert paper.units[0].unit_id == "elife-65180-pmc-s3#sec1-p1"
    assert paper.units[0].section_path == ("Introduction",)
    assert all(u.can_rewrite for u in paper.units)
    passage = paper.passage
    assert passage is not None
    assert passage.status == "PROPOSED"
    assert 350 // 2 <= passage.words <= 650
    assert passage.paragraph_ids[0] == "sec1-p1"


def test_fixture_without_machine_readable_licence_is_refused() -> None:
    """The Europe PMC copy has only licence prose: no passage, no rewritable unit."""
    source = next(s for s in fixture_sources(RBCORE_FIXTURES_DIR) if "europepmc" in s.paper_key)
    assert source.evidence == ()
    paper = ingest_paper(source)
    assert not paper.usable
    assert paper.passage is None
    assert not any(u.can_rewrite for u in paper.units)
    assert any("no machine-readable licence" in r for r in paper.licence_reasons)


def test_conflicting_primary_source_evidence_fails_closed() -> None:
    """A primary-source code that disagrees with the JATS licence blocks the paper."""
    source = next(s for s in fixture_sources(RBCORE_FIXTURES_DIR) if "65180" in s.paper_key)
    conflicting = PaperSource(
        source.paper_key,
        source.jats,
        (EvidenceRecord("pmc:license_code", "CC BY-ND", "synthetic", "2026-10-13"),),
    )
    paper = ingest_paper(conflicting)
    assert not paper.usable
    assert paper.passage is None


def test_ingest_outputs_round_trip(tmp_path: Path) -> None:
    """Units and passages written to disk load back and resolve."""
    papers = [ingest_paper(s) for s in fixture_sources(RBCORE_FIXTURES_DIR)]
    write_ingest(tmp_path, papers)
    units = load_units(tmp_path)
    passages = load_passages(tmp_path)
    assert len(passages) == sum(p.passage is not None for p in papers) == 3
    resolved = passage_units(passages[0], units)
    assert [u.paragraph_id for u in resolved] == list(passages[0].paragraph_ids)
    records = (tmp_path / "papers.jsonl").read_text(encoding="utf-8").splitlines()
    first = json.loads(records[0])
    assert first["evidence"][0]["field"] == "pmc:license_code"
    assert first["evidence"][0]["retrieved"] == "2026-10-13"
