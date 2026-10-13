"""Tests of the JATS parser on small SYNTHETIC snippets.

Every XML document in this file is synthetic: written by hand for the test,
not taken from any real article. Real-article tests live in
test_jats_fixtures.py.
"""

from __future__ import annotations

import pytest

from rbcore.jats import Article, JatsParseError, parse_jats
from rbcore.licences import LicenceField, decide

XLINK = 'xmlns:xlink="http://www.w3.org/1999/xlink"'
ALI = 'xmlns:ali="http://www.niso.org/schemas/ali/1.0/"'


def synthetic(body: str = "", meta: str = "", back: str = "", extra: str = "") -> Article:
    """Parse a synthetic article assembled from the given fragments.

    Args:
        body: Content of <body>.
        meta: Extra content of <article-meta>.
        back: Content of <back>.
        extra: Elements appended after <back> (e.g. sub-article).

    Returns:
        The parsed synthetic article.
    """
    xml = (
        f'<article {XLINK} {ALI} article-type="research-article" xml:lang="en">'
        "<front><journal-meta><journal-title-group><journal-title>Synthetic Journal"
        "</journal-title></journal-title-group></journal-meta>"
        "<article-meta><title-group><article-title>Synthetic <italic>test</italic> article"
        f"</article-title></title-group>{meta}</article-meta></front>"
        f"<body>{body}</body><back>{back}</back>{extra}</article>"
    )
    return parse_jats(xml.encode("utf-8"))


def test_nested_section_ids_are_positional() -> None:
    """Sections nest as sec1, sec1.1, sec1.1.1; paragraphs are numbered per section."""
    article = synthetic(
        "<p>Lead.</p>"
        "<sec id='s1'><title>One</title><p>A.</p><p>B.</p>"
        "<sec><title>One.one</title><p>C.</p><sec><p>D.</p></sec></sec>"
        "<sec><p>E.</p></sec></sec>"
        "<sec><title>Two</title><p>F.</p></sec>"
    )
    ids = {p.id: p.text for p in article.iter_paragraphs()}
    assert ids == {
        "body-p1": "Lead.",
        "sec1-p1": "A.",
        "sec1-p2": "B.",
        "sec1.1-p1": "C.",
        "sec1.1.1-p1": "D.",
        "sec1.2-p1": "E.",
        "sec2-p1": "F.",
    }
    assert article.title == "Synthetic test article"
    assert article.body.sections[0].xml_id == "s1"


def test_ids_do_not_depend_on_publisher_ids() -> None:
    """Changing or removing @id attributes does not change the stable IDs."""
    with_ids = synthetic("<sec id='x9'><p id='para7'>A.</p></sec>")
    without_ids = synthetic("<sec><p>A.</p></sec>")
    assert [p.id for p in with_ids.iter_paragraphs()] == ["sec1-p1"]
    assert [p.id for p in without_ids.iter_paragraphs()] == ["sec1-p1"]


def test_lists_quotes_definitions_and_boxes_become_blocks() -> None:
    """Each list item, quoted paragraph, definition and boxed paragraph is its own block."""
    article = synthetic(
        "<sec><p>Intro.</p>"
        "<list><list-item><p>First item.</p></list-item>"
        "<list-item><p>Second.</p></list-item></list>"
        "<disp-quote><p>Quoted.</p></disp-quote>"
        "<def-list><def-item><term>RCT</term>"
        "<def><p>Randomised trial.</p></def></def-item></def-list>"
        "<boxed-text><sec><title>Box</title><p>Boxed.</p></sec></boxed-text>"
        "</sec>"
    )
    blocks = [(p.id, p.kind, p.text) for p in article.iter_paragraphs()]
    assert blocks == [
        ("sec1-p1", "p", "Intro."),
        ("sec1-p2", "list-item", "First item."),
        ("sec1-p3", "list-item", "Second."),
        ("sec1-p4", "quote", "Quoted."),
        ("sec1-p5", "def", "RCT: Randomised trial."),
        ("sec1-p6", "boxed", "Boxed."),
    ]


def test_inline_markup_is_flattened_readably() -> None:
    """Italics vanish, superscripts read as ^ or [cite], formulas use TeX, floats are skipped."""
    article = synthetic(
        "<p>The <italic>MreB</italic> gene rose 10<sup>5</sup>-fold in Ca<sup>2+</sup> buffer"
        "<sup><xref ref-type='bibr' rid='b1'>1</xref>,<xref ref-type='bibr' rid='b2'>2</xref></sup>"
        " with <inline-formula><tex-math>p &lt; 0.05</tex-math></inline-formula> and "
        "<inline-formula><mml:math xmlns:mml='http://www.w3.org/1998/Math/MathML' alttext='n = 12'>"
        "<mml:mi>n</mml:mi></mml:math></inline-formula> "
        "(see <xref ref-type='fig' rid='f1'>Figure 1</xref>)."
        "<fig id='f1'><caption><p>Caption text must not leak.</p></caption></fig>"
        " CO<sub>2</sub> levels<break/>rose.</p>"
    )
    (paragraph,) = article.iter_paragraphs()
    assert paragraph.text == (
        "The MreB gene rose 10^5-fold in Ca^2+ buffer[1,2] with p < 0.05 and n = 12 "
        "(see Figure 1). CO2 levels rose."
    )


def test_alternatives_use_first_rendering_only() -> None:
    """Content inside <alternatives> is not duplicated."""
    article = synthetic(
        "<p>Value <inline-formula><alternatives><tex-math>x^2</tex-math>"
        "<mml:math xmlns:mml='http://www.w3.org/1998/Math/MathML'><mml:mi>x</mml:mi></mml:math>"
        "</alternatives></inline-formula>.</p>"
    )
    assert next(article.iter_paragraphs()).text == "Value x^2."


def test_abstracts_including_digest_and_structured_sections() -> None:
    """All abstracts are kept in order; structured abstract sections get abs-rooted IDs."""
    article = synthetic(
        meta=(
            "<abstract><sec><title>Background</title><p>Why.</p></sec>"
            "<sec><title>Results</title><p>What.</p></sec></abstract>"
            "<abstract abstract-type='executive-summary'><title>eLife digest</title>"
            "<p>Plain words.</p></abstract>"
        )
    )
    main, digest = article.abstracts
    assert article.abstract is main
    assert [p.id for p in main.iter_paragraphs()] == ["abs1.sec1-p1", "abs1.sec2-p1"]
    assert main.sections[0].title == "Background"
    assert digest.sec_type == "executive-summary"
    assert digest.title == "eLife digest"
    assert article.paragraph("abs2-p1").text == "Plain words."


def test_back_matter_sections_and_appendices() -> None:
    """ack, app (inside app-group) and back sec become back.secN; ref-list is skipped."""
    article = synthetic(
        "<p>Body.</p>",
        back=(
            "<ack><title>Acknowledgements</title><p>Thanks.</p></ack>"
            "<app-group><app><title>Appendix 1</title><p>Extra.</p>"
            "<sec><p>Deeper.</p></sec></app></app-group>"
            "<ref-list><ref><mixed-citation>Ref.</mixed-citation></ref></ref-list>"
            "<sec sec-type='data-availability'><title>Data</title><p>Open.</p></sec>"
        ),
    )
    assert [(s.id, s.kind, s.title) for s in article.back.sections] == [
        ("back.sec1", "ack", "Acknowledgements"),
        ("back.sec2", "app", "Appendix 1"),
        ("back.sec3", "sec", "Data"),
    ]
    assert article.paragraph("back.sec2.1-p1").text == "Deeper."
    assert [p.id for p in article.iter_paragraphs()] == ["body-p1"]


def test_sub_articles_are_ignored() -> None:
    """Peer-review sub-articles never contribute paragraphs, figures or COI text."""
    article = synthetic(
        "<p>Main.</p>",
        extra=(
            "<sub-article article-type='decision-letter'><front-stub/>"
            "<body><p>Decision letter text.</p><fig><caption><p>F</p></caption></fig>"
            "<fn fn-type='COI-statement'><p>Reviewer COI.</p></fn></body></sub-article>"
        ),
    )
    assert [p.text for p in article.iter_paragraphs()] == ["Main."]
    assert article.figures == ()
    assert article.coi_statements == ()


def test_figures_and_tables_numbered_with_their_sections() -> None:
    """Floats are numbered in document order across body and back, with section IDs."""
    article = synthetic(
        "<sec><p>See <xref ref-type='fig' rid='f1'>Figure 1</xref>.</p>"
        "<fig id='f1'><label>Figure 1.</label><caption><title>Title one.</title>"
        "<p>Caption one.</p></caption><graphic xlink:href='f1.tif'/></fig>"
        "<p>Para with float <fig id='f2'><label>Figure 2.</label>"
        "<caption><p>Two.</p></caption></fig>"
        "inside.</p>"
        "<table-wrap id='t1'><label>Table 1.</label><caption><p>Table caption.</p></caption>"
        "<table><tr><td>1</td></tr></table>"
        "<table-wrap-foot><fn><label>a</label><p>Footnote.</p></fn></table-wrap-foot></table-wrap>"
        "<sec><fig id='f3'><caption><p>Three.</p></caption></fig></sec></sec>",
        back=(
            "<app-group><app><fig id='fa'><caption><p>Appendix fig.</p></caption></fig>"
            "</app></app-group>"
        ),
    )
    assert [(f.id, f.xml_id, f.section_id) for f in article.figures] == [
        ("fig1", "f1", "sec1"),
        ("fig2", "f2", "sec1"),
        ("fig3", "f3", "sec1.1"),
        ("fig4", "fa", "back.sec1"),
    ]
    fig1 = article.figures[0]
    assert (fig1.label, fig1.caption_title, fig1.caption, fig1.graphics) == (
        "Figure 1.",
        "Title one.",
        "Caption one.",
        ("f1.tif",),
    )
    (table,) = article.tables
    assert (table.id, table.caption, table.footnotes) == (
        "table1",
        "Table caption.",
        ("Footnote.",),
    )
    # Figure content never leaks into paragraph text.
    assert article.paragraph("sec1-p2").text == "Para with float inside."


def test_figure_permissions_fields_are_kept_separately() -> None:
    """Each licence field (href, ali ref, license-type, prose) is recorded on its own."""
    article = synthetic(
        "<fig><caption><p>C.</p></caption><permissions>"
        "<copyright-statement>© 2010 Example Press</copyright-statement>"
        "<copyright-year>2010</copyright-year><copyright-holder>Example Press</copyright-holder>"
        "<license license-type='open-access' xlink:href='http://creativecommons.org/licenses/by-nd/4.0/'>"
        "<ali:license_ref specific-use='vor'>https://creativecommons.org/licenses/by-nd/4.0/</ali:license_ref>"
        "<license-p>Reproduced under "
        "<ext-link xlink:href='https://example.org'>CC BY-ND</ext-link>.</license-p>"
        "</license></permissions></fig>"
    )
    permissions = article.figures[0].permissions
    assert permissions is not None
    assert permissions.copyright_statement == "© 2010 Example Press"
    assert permissions.copyright_years == ("2010",)
    (statement,) = permissions.licences
    assert statement.xlink_href == "http://creativecommons.org/licenses/by-nd/4.0/"
    assert statement.ali_license_refs == ("https://creativecommons.org/licenses/by-nd/4.0/",)
    assert statement.ali_specific_uses == ("vor",)
    assert statement.license_type == "open-access"
    assert statement.prose == "Reproduced under CC BY-ND."
    assert [e.field for e in permissions.evidence()] == [
        LicenceField.JATS_ALI_LICENSE_REF,
        LicenceField.JATS_LICENSE_XLINK_HREF,
        LicenceField.JATS_LICENSE_TYPE,
        LicenceField.JATS_LICENSE_P,
    ]


def test_ali_license_ref_directly_in_permissions_is_read() -> None:
    """JATS 1.1+ allows ali:license_ref as a direct child of <permissions>."""
    article = synthetic(
        meta=(
            "<permissions><ali:free_to_read/>"
            "<ali:license_ref>http://creativecommons.org/publicdomain/zero/1.0/</ali:license_ref>"
            "</permissions>"
        )
    )
    assert article.permissions is not None
    assert article.permissions.free_to_read
    decision = decide(article.permissions.evidence())
    assert decision.permissions.can_rewrite
    assert decision.source_field is LicenceField.JATS_ALI_LICENSE_REF


def test_conflicting_article_licences_fail_closed() -> None:
    """Two <license> elements naming different families send the article to review."""
    article = synthetic(
        meta=(
            "<permissions>"
            "<license xlink:href='http://creativecommons.org/licenses/by/4.0/'/>"
            "<license xlink:href='http://creativecommons.org/licenses/by-nc-nd/4.0/'/>"
            "</permissions>"
        )
    )
    assert article.permissions is not None
    decision = decide(article.permissions.evidence())
    assert not decision.permissions.can_display
    assert decision.needs_review


def test_identifier_and_date_variants() -> None:
    """Bare-digit pmc IDs gain a PMC prefix; DOI URLs are stripped; month names parse."""
    article = synthetic(
        meta=(
            "<article-id pub-id-type='pmc'>12345</article-id>"
            "<article-id pub-id-type='doi'>https://doi.org/10.1234/ABC.5</article-id>"
            "<article-id pub-id-type='pmid'>999</article-id>"
            "<article-id pub-id-type='manuscript'>NIHMS1</article-id>"
            "<pub-date date-type='pub' publication-format='print'>"
            "<month>Sept</month><year>2020</year></pub-date>"
            "<pub-date pub-type='epub'><day>5</day><month>13</month><year>2019</year></pub-date>"
        )
    )
    ids = article.identifiers
    assert (ids.pmcid, ids.doi, ids.pmid) == ("PMC12345", "10.1234/ABC.5", "999")
    assert ids.other == (("manuscript", "NIHMS1"),)
    print_date, epub = article.publication_dates
    assert (print_date.kind, print_date.iso) == ("pub/print", "2020-09")
    assert epub.month is None  # month 13 is invalid
    assert article.published is epub  # electronic preferred
    assert epub.iso == "2019"


def test_authors_collab_orcid_and_corresponding() -> None:
    """Structured names, group authors (without member lists) and ORCIDs are parsed."""
    article = synthetic(
        meta=(
            "<contrib-group>"
            "<contrib contrib-type='author' corresp='yes'><contrib-id contrib-id-type='orcid'>"
            "https://orcid.org/0000-0000-0000-0000</contrib-id><name><surname>Doe</surname>"
            "<given-names>Jane</given-names></name></contrib>"
            "<contrib contrib-type='author'><collab>Synthetic Consortium"
            "<contrib-group><contrib><name><surname>Member</surname></name></contrib></contrib-group>"
            "</collab></contrib>"
            "<contrib contrib-type='author'><string-name>J. Q. Literal</string-name></contrib>"
            "<contrib contrib-type='editor'><name><surname>Editor</surname></name></contrib>"
            "</contrib-group>"
        )
    )
    first, group, literal = article.authors
    assert (first.display_name, first.orcid, first.corresponding) == (
        "Jane Doe",
        "https://orcid.org/0000-0000-0000-0000",
        True,
    )
    assert group.display_name == "Synthetic Consortium"
    assert (literal.literal, literal.display_name) == ("J. Q. Literal", "J. Q. Literal")


def test_coi_and_funding_sources() -> None:
    """COI from fn-type variants, conflict and titled sections; funding from groups and sections."""
    article = synthetic(
        "<p>Body.</p>",
        meta=(
            "<author-notes><fn fn-type='COI-statement'><label>*</label><p>None declared.</p></fn>"
            "</author-notes><conflict>Old-style conflict.</conflict>"
            "<funding-group><award-group><funding-source><institution-wrap>"
            "<institution-id institution-id-type='FundRef'>http://dx.doi.org/10.13039/1</institution-id>"
            "<institution>Synthetic Fund</institution></institution-wrap></funding-source>"
            "<award-id>G-1</award-id></award-group>"
            "<funding-statement>Funded by Synthetic Fund.</funding-statement></funding-group>"
        ),
        back=(
            "<sec><title>Competing interests</title><p>Author B consults for X.</p></sec>"
            "<fn-group><fn fn-type='financial-disclosure'><p>Grant G-1.</p></fn></fn-group>"
            "<sec sec-type='funding'><title>Support</title><p>Also funded by Y.</p></sec>"
        ),
    )
    assert article.coi_statements == (
        "None declared.",
        "Old-style conflict.",
        "Author B consults for X.",
    )
    assert article.funding.awards[0].sources == ("Synthetic Fund",)
    assert article.funding.awards[0].award_ids == ("G-1",)
    assert article.funding.statements == (
        "Funded by Synthetic Fund.",
        "Grant G-1.",
        "Also funded by Y.",
    )
    assert not article.funding.is_empty


def test_missing_parts_give_empty_values() -> None:
    """An article with no body, permissions, COI or funding parses to empty values."""
    article = parse_jats(b"<article><front><article-meta/></front></article>")
    assert article.body.paragraphs == ()
    assert article.body.sections == ()
    assert article.permissions is None
    assert article.abstract is None
    assert article.published is None
    assert article.coi_statements == ()
    assert article.funding.is_empty
    with pytest.raises(KeyError):
        article.paragraph("body-p1")


def test_pmc_articleset_wrapper_is_unwrapped() -> None:
    """E-utilities efetch wraps articles in <pmc-articleset>."""
    article = parse_jats(
        b"<pmc-articleset><article><front><article-meta><title-group>"
        b"<article-title>Wrapped</article-title></title-group></article-meta></front></article>"
        b"</pmc-articleset>"
    )
    assert article.title == "Wrapped"


def test_non_article_root_is_rejected() -> None:
    """Documents that are not JATS articles raise JatsParseError."""
    with pytest.raises(JatsParseError, match="expected <article>"):
        parse_jats(b"<html><body/></html>")
