"""Tests of study-type classification, the selection config and the shortlist pipeline.

Every network response here is SYNTHETIC, served by httpx.MockTransport.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from rbbench.paths import SELECTION_DIR
from rbbench.selection.classify import StudyType, classify, design_evidence
from rbbench.selection.config import SelectionConfig, SelectionConfigError, load_selection_config
from rbbench.selection.shortlist import (
    CANDIDATE_COLUMNS,
    build_shortlist,
    read_candidates,
    screening_order,
    write_candidates,
    write_screening_log,
)
from rbbench.sources.eutils import EutilsClient, EutilsError
from rbcore.http import PoliteFetcher, RateLimiter

# ----- classification ---------------------------------------------------------


def test_classify_uses_publication_types_then_jats() -> None:
    """A trial typed by PubMed and the publisher is a randomised trial."""
    result = classify(
        ["Journal Article", "Randomized Controlled Trial"],
        "research-article",
        lab_query_match=False,
    )
    assert result.study_type is StudyType.RANDOMISED_TRIAL
    assert "JATS article-type: research-article" in result.basis


def test_classify_refuses_mixed_or_disagreeing_evidence() -> None:
    """Two designs at once, or a JATS type that disagrees, leaves it unclassified."""
    mixed = classify(
        ["Randomized Controlled Trial", "Systematic Review"], None, lab_query_match=False
    )
    assert mixed.study_type is None
    assert "ambiguous" in mixed.basis
    editorial = classify(["Review"], "editorial", lab_query_match=False)
    assert editorial.study_type is None


def test_lab_needs_the_lab_query_and_no_clinical_type() -> None:
    """Lab/mechanistic comes only from the lab search, never with clinical types."""
    assert (
        classify(["Journal Article"], "research-article", lab_query_match=True).study_type
        is StudyType.LAB_MECHANISTIC
    )
    assert classify(["Journal Article"], None, lab_query_match=False).study_type is None
    assert (
        classify(["Journal Article", "Case Reports"], None, lab_query_match=True).study_type is None
    )


def test_design_evidence_confirms_design_and_rejects_secondary_analyses() -> None:
    """The abstract must name the design; trial slots exclude post hoc analyses."""
    assert design_evidence(StudyType.RANDOMISED_TRIAL, "We randomly assigned 40 adults") == (
        "randomly assigned"
    )
    assert (
        design_evidence(
            StudyType.RANDOMISED_TRIAL, "A post hoc analysis of a randomized controlled trial"
        )
        is None
    )
    assert design_evidence(StudyType.REVIEW, "We performed a meta-analysis") == "meta-analysis"
    assert design_evidence(StudyType.OBSERVATIONAL, "A modelling study") is None


# ----- config -------------------------------------------------------------------


def test_committed_config_has_twelve_slots_across_four_types() -> None:
    """slots_v1: 12 slots, 3 per study type, 2 candidates each, PROPOSED."""
    config = load_selection_config(SELECTION_DIR / "slots_v1.yaml")
    assert config.status == "PROPOSED"
    assert len(config.slots) == 12
    for study_type in StudyType:
        assert sum(s.study_type is study_type for s in config.slots) == 3
    assert config.candidates_per_slot == 2
    query = config.query_for(config.slots[0])
    assert query.startswith('("eLife"[ta]) AND ("Randomized Controlled Trial"[pt])')
    assert query.endswith('2015:2022[dp] AND "pubmed pmc"[sb]')


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (('date_range: "2015:2022"', 'date_range: "2015"'), "date_range"),
        (("journals: [elife]}", "journals: [nope]}"), "unknown journals"),
        (("candidates_per_slot: 2", "candidates_per_slot: 0"), "candidates_per_slot"),
        (("- {id: S02,", "- {id: S01,"), "duplicate"),
    ],
)
def test_invalid_config_is_rejected(tmp_path: Path, change: tuple[str, str], message: str) -> None:
    """Broken configs are refused with a message naming the problem."""
    text = (SELECTION_DIR / "slots_v1.yaml").read_text(encoding="utf-8")
    assert change[0] in text
    path = tmp_path / "slots.yaml"
    path.write_text(text.replace(change[0], change[1], 1), encoding="utf-8")
    with pytest.raises(SelectionConfigError, match=message):
        load_selection_config(path)


def test_screening_order_is_seeded_and_deterministic() -> None:
    """The order depends only on the seed and the PMIDs, not on input order."""
    pmids = ["3", "1", "2", "1"]
    first = screening_order(pmids, "seed")
    assert first == screening_order(list(reversed(pmids)), "seed")
    assert sorted(first) == ["1", "2", "3"]
    expected = sorted(
        ["1", "2", "3"], key=lambda p: hashlib.sha256(f"seed:{p}".encode()).hexdigest()
    )
    assert first == expected


# ----- the pipeline against synthetic responses ---------------------------------

_SYNTHETIC_WORDS = " ".join(["synthetic"] * 60)


def synthetic_jats(*, abstract: str, lay_summary: bool = True, licence: str = "by/4.0") -> bytes:
    """Build a SYNTHETIC JATS article with a Discussion section."""
    digest = (
        '<abstract abstract-type="executive-summary"><title>eLife digest</title>'
        "<p>Synthetic lay summary.</p></abstract>"
        if lay_summary
        else ""
    )
    body = "".join(f"<p>{_SYNTHETIC_WORDS} paragraph {i}.</p>" for i in range(3))
    return (
        '<article article-type="research-article" xmlns:xlink="http://www.w3.org/1999/xlink">'
        "<front><article-meta><title-group><article-title>Synthetic</article-title>"
        "</title-group><permissions><license "
        f'xlink:href="https://creativecommons.org/licenses/{licence}/">'
        "<license-p>Synthetic licence text.</license-p></license></permissions>"
        f"<abstract><p>{abstract}</p></abstract>{digest}</article-meta></front>"
        f"<body><sec><title>Results</title>{body}</sec>"
        f"<sec><title>Discussion</title>{body}</sec></body></article>"
    ).encode()


def _summary(pmid: str, pmcid: str | None, pubtypes: list[str]) -> dict[str, object]:
    """A SYNTHETIC esummary record."""
    ids = [{"idtype": "pubmed", "value": pmid}]
    if pmcid:
        ids.append({"idtype": "pmc", "value": pmcid})
    return {
        "uid": pmid,
        "title": f"Synthetic {pmid}",
        "source": "Elife",
        "pubdate": "2020 Jan 1",
        "pubtype": pubtypes,
        "articleids": ids,
    }


class SyntheticServer:
    """Serves SYNTHETIC E-utilities and PMC Cloud Service responses."""

    def __init__(self) -> None:
        """Define five synthetic PMIDs covering accept and reject paths."""
        trial = ["Journal Article", "Randomized Controlled Trial"]
        self.summaries = {
            "1": _summary("1", "PMC1", trial),
            "2": _summary("2", "PMC2", trial),
            "3": _summary("3", None, trial),
            "4": _summary("4", "PMC4", ["Journal Article", "Review"]),
            "5": _summary("5", "PMC5", trial),
        }
        randomised = "Adults were randomly assigned to synthetic drug or placebo."
        self.jats = {
            "PMC1": synthetic_jats(abstract=randomised),
            "PMC2": synthetic_jats(abstract=randomised, licence="by-nd/4.0"),
            "PMC5": synthetic_jats(abstract=randomised, lay_summary=False),
        }
        self.codes = {"PMC1": "CC BY", "PMC2": "CC BY", "PMC5": "CC BY"}
        self.requests: list[str] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Route one request to its synthetic response."""
        url = str(request.url)
        self.requests.append(url)
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        assert "mailto" not in url
        assert "email" not in query
        if parts.path.endswith("esearch.fcgi"):
            body = {"esearchresult": {"idlist": list(self.summaries), "count": "5"}}
            return httpx.Response(200, json=body)
        if parts.path.endswith("esummary.fcgi"):
            ids = query["id"][0].split(",")
            result = {"uids": ids, **{i: self.summaries[i] for i in ids}}
            return httpx.Response(200, json={"result": result})
        if parts.path == "/" and "list-type" in query:
            pmcid = query["prefix"][0].rstrip(".")
            listing = (
                '<?xml version="1.0"?><ListBucketResult '
                'xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><CommonPrefixes>'
                f"<Prefix>{pmcid}.1/</Prefix></CommonPrefixes></ListBucketResult>"
            )
            return httpx.Response(200, content=listing.encode())
        key = parts.path.strip("/").split("/")[0]
        pmcid = key.split(".")[0]
        if parts.path.endswith(".json"):
            xml = self.jats[pmcid]
            md5 = hashlib.md5(xml, usedforsecurity=False).hexdigest()
            record = {
                "pmcid": pmcid,
                "version": 1,
                "pmid": int(pmcid[3:]),
                "doi": f"10.0/{pmcid}",
                "title": "Synthetic",
                "citation": "Synthetic",
                "is_pmc_openaccess": True,
                "is_manuscript": False,
                "is_retracted": False,
                "license_code": self.codes[pmcid],
                "xml_url": f"s3://pmc-oa-opendata/{key}/{key}.xml?md5={md5}",
            }
            return httpx.Response(200, json=record)
        if parts.path.endswith(".xml"):
            return httpx.Response(200, content=self.jats[pmcid])
        return httpx.Response(404)


@pytest.fixture
def synthetic_config() -> SelectionConfig:
    """The committed config cut down to one trial slot with small bounds."""
    config = load_selection_config(SELECTION_DIR / "slots_v1.yaml")
    return replace(
        config,
        slots=config.slots[:1],
        min_body_words=100,
        max_body_words=1000,
        max_screen_per_slot=5,
    )


@pytest.fixture
def fetcher_for(tmp_path: Path) -> Callable[[SyntheticServer], PoliteFetcher]:
    """Return a factory for a non-sleeping fetcher backed by a synthetic server."""

    def build(server: SyntheticServer) -> PoliteFetcher:
        """Create the fetcher."""
        return PoliteFetcher(
            cache_dir=tmp_path / "cache",
            transport=httpx.MockTransport(server.handler),
            rate_limiter=RateLimiter(sleep=lambda _seconds: None),
            sleep=lambda _seconds: None,
        )

    return build


def test_shortlist_screens_in_order_and_records_licence_evidence(
    synthetic_config: SelectionConfig,
    fetcher_for: Callable[[SyntheticServer], PoliteFetcher],
    tmp_path: Path,
) -> None:
    """Only the CC BY trial with a lay summary is accepted; every reject has a reason."""
    server = SyntheticServer()
    with fetcher_for(server) as fetcher:
        shortlist = build_shortlist(synthetic_config, EutilsClient(fetcher), fetcher)

    (candidate,) = shortlist.candidates
    assert (candidate.pmcid, candidate.option, candidate.status) == ("PMC1", "A", "PROPOSED")
    assert candidate.licence_field == "pmc:license_code"
    assert candidate.licence_raw_value == "CC BY"
    assert candidate.licence_url == "https://pmc-oa-opendata.s3.amazonaws.com/PMC1.1/PMC1.1.json"
    assert len(candidate.licence_retrieved) == 10
    assert candidate.can_rewrite
    assert candidate.can_display
    assert "randomly assigned" in candidate.classification_basis
    assert candidate.paper_key == "PMC1.1"
    assert shortlist.unfilled == ["S01"]

    reasons = {r.pmid: r.reason for r in shortlist.screening if r.outcome == "rejected"}
    assert reasons["3"] == "no PMC copy"
    assert reasons["4"] == "classified as review, slot needs randomised_trial"
    assert "conflicting licence values" in reasons["2"]
    assert "no expert lay summary" in reasons["5"]

    # Outputs round-trip through CSV.
    path = tmp_path / "candidates.csv"
    write_candidates(path, shortlist.candidates)
    assert read_candidates(path) == shortlist.candidates
    header = path.read_text(encoding="utf-8").splitlines()[0]
    assert header == ",".join(CANDIDATE_COLUMNS)
    write_screening_log(tmp_path / "screening.csv", shortlist.screening)
    assert len((tmp_path / "screening.csv").read_text().splitlines()) == 6


def test_rerun_is_served_from_the_cache(
    synthetic_config: SelectionConfig, fetcher_for: Callable[[SyntheticServer], PoliteFetcher]
) -> None:
    """A second run makes no new requests and reproduces the same shortlist."""
    server = SyntheticServer()
    with fetcher_for(server) as fetcher:
        first = build_shortlist(synthetic_config, EutilsClient(fetcher), fetcher)
    count = len(server.requests)
    with fetcher_for(server) as fetcher:
        second = build_shortlist(synthetic_config, EutilsClient(fetcher), fetcher)
    assert len(server.requests) == count
    assert second == first


def test_eutils_api_key_is_sent_but_never_leaks_into_errors(tmp_path: Path) -> None:
    """The optional key reaches NCBI but is redacted from error messages."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        """Record the URL and fail."""
        seen.append(str(request.url))
        return httpx.Response(400)

    fetcher = PoliteFetcher(
        cache_dir=None,
        transport=httpx.MockTransport(handler),
        rate_limiter=RateLimiter(sleep=lambda _s: None),
    )
    client = EutilsClient(fetcher, api_key="secret-key")
    with pytest.raises(EutilsError, match="api_key=\\*\\*\\*") as raised:
        client.esearch("x")
    assert "secret-key" not in str(raised.value)
    assert "api_key=secret-key" in seen[0]
    assert "tool=ResearchBridge-dev" in seen[0]
    assert json.dumps(seen).count("@") == 0
