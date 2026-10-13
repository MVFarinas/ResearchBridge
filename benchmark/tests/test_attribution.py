"""Tests of the attribution lines shown beside source text in rater packets."""

from __future__ import annotations

import pytest

from rbbench.attribution import NLM_ACKNOWLEDGEMENT, AttributionError, attribution_line
from rbbench.ingest import ingest_paper
from rbbench.paths import RBCORE_FIXTURES_DIR
from rbbench.sources.papers import fixture_sources


def test_pmc_fixture_is_attributed_with_doi_licence_source_and_nlm() -> None:
    """A PMC copy names its title, journal, DOI, licence, source URL and credits NLM."""
    source = next(s for s in fixture_sources(RBCORE_FIXTURES_DIR) if "65180" in s.paper_key)
    paper = ingest_paper(source).to_record()
    line = attribution_line(paper)
    assert line.startswith(f"{paper['title'].rstrip('.')}. {paper['journal']}. ")
    assert "https://doi.org/10.7554/eLife.65180." in line
    assert "Licence: CC BY." in line
    assert "Source: https://pmc-oa-opendata.s3.amazonaws.com/PMC7853715.1/" in line
    assert line.endswith(NLM_ACKNOWLEDGEMENT)


def test_non_pmc_record_gets_no_nlm_credit() -> None:
    """Without PMC licence evidence the NLM acknowledgement is not claimed."""
    record = {
        "paper_key": "synthetic",
        "title": "A SYNTHETIC title",
        "licence": "CC0",
        "evidence": [{"field": "europepmc:license", "value": "cc0"}],
        "metadata": {},
    }
    assert attribution_line(record) == "A SYNTHETIC title. Licence: CC0."


@pytest.mark.parametrize("missing", ["title", "licence"])
def test_record_without_title_or_licence_is_refused(missing: str) -> None:
    """An attribution needs at least the title and the licence."""
    record = {"paper_key": "synthetic", "title": "A SYNTHETIC title", "licence": "CC BY"}
    record[missing] = ""
    with pytest.raises(AttributionError, match="no title or licence"):
        attribution_line(record)
