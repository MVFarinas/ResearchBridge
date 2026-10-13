"""Tests of the JATS parser and licence gate against real CC BY fixtures.

See tests/fixtures/jats/README.md for the articles and their attribution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

import pytest

from rbcore.jats import Article, parse_jats_file
from rbcore.licences import (
    NO_PERMISSIONS,
    Licence,
    LicenceEvidence,
    LicenceFamily,
    LicenceField,
    decide,
    decide_part,
)

Loader = Callable[[str], Article]


def test_fixtures_match_manifest_checksums(fixture_dir: Path) -> None:
    """Fixtures are verbatim copies: their SHA-256 matches the recorded manifest."""
    manifest = json.loads((fixture_dir / "manifest.json").read_text(encoding="utf-8"))
    files = {entry["file"]: entry["sha256"] for entry in manifest["fixtures"]}
    assert files.keys() == {p.name for p in fixture_dir.glob("*.xml")}
    for name, digest in files.items():
        assert hashlib.sha256((fixture_dir / name).read_bytes()).hexdigest() == digest, name


def test_reparsing_yields_identical_ids(fixture_dir: Path) -> None:
    """IDs are deterministic: two independent parses produce identical structures."""
    for path in sorted(fixture_dir.glob("*.xml")):
        first, second = parse_jats_file(path), parse_jats_file(path)
        assert first == second
        assert [p.id for p in first.iter_paragraphs()] == [p.id for p in second.iter_paragraphs()]


def test_paragraph_ids_are_unique(fixture_dir: Path) -> None:
    """No two paragraphs in an article share an ID."""
    for path in sorted(fixture_dir.glob("*.xml")):
        article = parse_jats_file(path)
        ids = [
            p.id
            for root in (*article.abstracts, article.body, article.back)
            for p in root.iter_paragraphs()
        ]
        assert len(ids) == len(set(ids)), path.name


# ----- PLOS publisher JATS --------------------------------------------------


def test_plos_metadata(load_article: Loader) -> None:
    """Identifiers, title, authors, journal and dates come from article-meta."""
    article = load_article("plos-pmed-1004542.xml")
    assert article.identifiers.doi == "10.1371/journal.pmed.1004542"
    assert article.identifiers.publisher_id == "PMEDICINE-D-25-00290"
    assert article.title == "Predatory journals: What can we do to protect their prey?"
    assert article.article_type == "editorial"
    assert article.subject_heading == "Editorial"
    assert article.language == "en"
    assert len(article.authors) == 16
    assert article.authors[0].display_name == "Christine Laine"
    assert article.journal.title == "PLOS Medicine"
    assert article.journal.nlm_ta == "PLoS Med"
    assert article.published is not None
    assert article.published.iso == "2025-04-02"


def test_plos_structure_and_ids(load_article: Loader) -> None:
    """Paragraphs before the first section live in ``body``; sections are sec1..secN."""
    article = load_article("plos-pmed-1004542.xml")
    assert article.body.paragraphs[0].id == "body-p1"
    assert [s.id for s in article.body.sections] == ["sec1", "sec2", "sec3"]
    assert article.body.sections[0].title == "What can authors do?"
    assert article.body.sections[0].paragraphs[0].id == "sec1-p1"
    assert article.body.sections[0].xml_id == "sec001"
    assert [s.id for s in article.back.sections] == ["back.sec1"]
    assert article.back.sections[0].title == "Disclosures"


def test_plos_text_is_flattened_with_citations(load_article: Loader) -> None:
    """Inline xrefs keep their text, so bracketed citations stay readable."""
    first = load_article("plos-pmed-1004542.xml").paragraph("body-p1")
    assert first.text.startswith("A growing number of entities misrepresent themselves")
    assert "publishing standards [1,2]." in first.text
    assert "<xref" not in first.text
    assert "  " not in first.text
    assert "<xref" in first.source_xml


def test_plos_licence_from_xlink_href(load_article: Loader) -> None:
    """PLOS records its licence in license/@xlink:href, which is machine-readable."""
    article = load_article("plos-pmed-1004542.xml")
    assert article.permissions is not None
    statement = article.permissions.licences[0]
    assert statement.xlink_href == "http://creativecommons.org/licenses/by/4.0/"
    assert statement.ali_license_refs == ()
    assert statement.prose is not None
    assert "Creative Commons Attribution License" in statement.prose
    decision = decide(article.permissions.evidence())
    assert decision.source_field is LicenceField.JATS_LICENSE_XLINK_HREF
    assert decision.licence == Licence(LicenceFamily.CC_BY, "4.0")
    assert decision.permissions.can_display
    assert decision.permissions.can_rewrite


def test_plos_coi_and_funding(load_article: Loader) -> None:
    """fn-type="conflict" and funding-statement are captured as raw text."""
    article = load_article("plos-pmed-1004542.xml")
    assert any(
        s.startswith("TB reports grants from the National Institutes of Health")
        for s in article.coi_statements
    )
    assert (
        article.funding.statements[0] == "The author(s) received no specific funding for this work."
    )
    assert article.funding.awards == ()


# ----- eLife via PMC Cloud Service ------------------------------------------


def test_elife_insight_from_pmc(load_article: Loader) -> None:
    """PMC's copy carries ali:license_ref; PMCID, PMID and DOI are all present."""
    article = load_article("elife-93719-pmc-s3.xml")
    assert article.identifiers.pmcid == "PMC10718527"
    assert article.identifiers.pmid == "38088194"
    assert ("pmcid-ver", "PMC10718527.1") in article.identifiers.other
    assert article.article_type == "article-commentary"
    assert article.permissions is not None
    assert article.permissions.free_to_read
    decision = decide(article.permissions.evidence())
    assert decision.source_field is LicenceField.JATS_ALI_LICENSE_REF
    assert decision.source is not None
    assert decision.source.specific_use == "textmining"
    assert decision.permissions.can_rewrite
    # The only machine-readable value is scoped to text mining, so a human (or an
    # agreeing unscoped value such as PMC's license_code) must confirm it.
    assert decision.needs_review
    assert "@specific-use (textmining)" in decision.reasons[-1]
    confirmed = decide(
        [
            *article.permissions.evidence(),
            LicenceEvidence(LicenceField.PMC_LICENSE_CODE, "CC BY"),
        ]
    )
    assert confirmed.permissions.can_rewrite
    assert not confirmed.needs_review
    assert article.coi_statements == ("No competing interests declared.",)


def test_elife_insight_figure_inherits_article_licence(load_article: Loader) -> None:
    """A figure without its own permissions block inherits the article decision."""
    article = load_article("elife-93719-pmc-s3.xml")
    assert article.permissions is not None
    (figure,) = article.figures
    assert figure.id == "fig1"
    assert figure.label == "Figure 1."
    assert figure.permissions == ()
    assert "elife-93719-fig1.jpg" in figure.graphics
    decision = decide_part(decide(article.permissions.evidence()), figure.permissions)
    assert decision.inherited
    assert decision.permissions.can_rewrite


def test_europe_pmc_copy_is_prose_only_and_fails_closed(load_article: Loader) -> None:
    """Europe PMC's copy of the same article has only license-p prose: fail closed."""
    article = load_article("elife-93719-europepmc.xml")
    assert article.identifiers.doi == "10.7554/eLife.93719"
    assert article.permissions is not None
    (statement,) = article.permissions.licences
    assert statement.xlink_href is None
    assert statement.ali_license_refs == ()
    assert statement.prose is not None
    assert "Creative Commons Attribution License" in statement.prose
    decision = decide(article.permissions.evidence())
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    # The COI footnote was moved into a body section by Europe PMC; it is still found.
    assert article.coi_statements == ("No competing interests declared.",)


def test_elife_review_figure_with_several_panel_licences_fails_closed(load_article: Loader) -> None:
    """Figure 1 of eLife 65180 has three permissions blocks, one per reproduced panel.

    Panel 1a (top) is CC BY-NC; panels 1a (bottom) and 1b are reproduced with
    permission and not covered by any licence. All three blocks are kept, and
    the figure as a whole fails closed rather than taking the first block's
    CC BY-NC licence.
    """
    article = load_article("elife-65180-pmc-s3.xml")
    assert article.permissions is not None
    article_decision = decide(article.permissions.evidence())
    assert article_decision.licence == Licence(LicenceFamily.CC_BY, "4.0")

    fig1, fig2 = article.figures
    assert [block.copyright_holders for block in fig1.permissions] == [
        ("Pandey et al",),
        ("Cheena Kapoor",),
        ("Friederike Ebner",),
    ]
    assert {block.context for block in fig1.permissions} == {"fig"}
    fig1_decision = decide_part(article_decision, fig1.permissions)
    assert fig1_decision.permissions == NO_PERMISSIONS
    assert fig1_decision.needs_review
    assert not fig1_decision.inherited
    assert "3 permissions blocks" in fig1_decision.reasons[0]

    # The first panel's own block, judged alone, is CC BY-NC.
    panel_decision = decide_part(article_decision, fig1.permissions[:1])
    assert panel_decision.licence == Licence(LicenceFamily.CC_BY_NC, "4.0")
    assert panel_decision.permissions.non_commercial
    assert panel_decision.permissions.can_display

    fig2_decision = decide_part(article_decision, fig2.permissions)
    assert fig2_decision.inherited
    assert not fig2_decision.permissions.non_commercial
    assert article.unattached_permissions == ()


def test_elife_review_figure_with_prose_only_permissions_fails_closed(load_article: Loader) -> None:
    """Figure 1 of eLife 61907 is "not covered by the CC-BY 4.0 licence": no display."""
    article = load_article("elife-61907-pmc-s3.xml")
    assert article.permissions is not None
    article_decision = decide(article.permissions.evidence())
    fig1 = article.figures[0]
    (fig1_block,) = fig1.permissions
    assert fig1_block.copyright_holders == ("USA TODAY NETWORK",)
    assert fig1_block.licences[0].prose is not None
    assert "not covered by the CC-BY 4.0 licence" in fig1_block.licences[0].prose
    decision = decide_part(article_decision, fig1.permissions)
    assert decision.permissions == NO_PERMISSIONS
    assert decision.needs_review
    # The other figure and the table still inherit the article's CC BY licence.
    assert decide_part(article_decision, article.figures[1].permissions).permissions.can_rewrite
    (table,) = article.tables
    assert table.id == "table1"
    assert table.kind == "table"
    assert decide_part(article_decision, table.permissions).inherited


def test_elife_review_sections_nest_and_figures_know_their_section(load_article: Loader) -> None:
    """Nested sections get dotted IDs; figures record the section they sit in."""
    article = load_article("elife-65180-pmc-s3.xml")
    intro = article.body.sections[0]
    assert intro.id == "sec1"
    assert intro.title == "Introduction"
    assert [s.id for s in intro.sections][:2] == ["sec1.1", "sec1.2"]
    assert intro.sections[0].paragraphs[0].id == "sec1.1-p1"
    assert article.figures[0].section_id == "sec1"
    assert article.abstract is not None
    assert article.abstract.id == "abs1"
    assert article.abstract.paragraphs[0].id == "abs1-p1"


def test_elife_review_funding_awards(load_article: Loader) -> None:
    """award-group yields funder and grant number; institution IDs are not in the text."""
    article = load_article("elife-65180-pmc-s3.xml")
    sources = [a.sources for a in article.funding.awards]
    assert sources[:2] == [("Wellcome Trust",), ("Wellcome Trust",)]
    assert article.funding.awards[0].award_ids == ("098565/Z/12/Z",)
    assert (
        "This paper was supported by the following grants: Wellcome Trust 098565/Z/12/Z "
        "to David Gems. Wellcome Trust 215574/Z/19/Z to David Gems." in article.funding.statements
    )
    assert not any("10.13039" in s for s in article.funding.statements)


@pytest.mark.parametrize(
    "name",
    [
        "elife-93719-pmc-s3.xml",
        "elife-93719-europepmc.xml",
        "elife-65180-pmc-s3.xml",
        "elife-61907-pmc-s3.xml",
        "plos-pmed-1004542.xml",
    ],
)
def test_no_empty_paragraphs_and_ids_follow_scheme(name: str, load_article: Loader) -> None:
    """Every paragraph has text and an ID under a known root (body, sec, abs, back)."""
    article = load_article(name)
    for root in (*article.abstracts, article.body, article.back):
        for paragraph in root.iter_paragraphs():
            assert paragraph.id.startswith(("body-p", "sec", "abs", "back."))
            assert paragraph.text.strip() == paragraph.text != ""
