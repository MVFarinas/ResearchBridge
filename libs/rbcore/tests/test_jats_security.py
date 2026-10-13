"""Security tests: the JATS parser must treat input as untrusted (all inputs synthetic)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from rbcore.jats import JatsParseError, parse_jats, parse_jats_file


def test_external_entity_is_not_resolved(tmp_path: Path) -> None:
    """XXE: an external entity pointing at a local file is never read; the parse fails."""
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET-CONTENT")
    xml = (
        f'<!DOCTYPE article [<!ENTITY xxe SYSTEM "{secret.as_uri()}">]>'
        "<article><body><p>Leak: &xxe;</p></body></article>"
    ).encode()
    with pytest.raises(JatsParseError, match="&xxe;") as excinfo:
        parse_jats(xml)
    assert "TOP-SECRET-CONTENT" not in str(excinfo.value)


def test_internal_entity_fails_loudly_instead_of_dropping_text() -> None:
    """An internal-subset entity is not expanded, so the parse fails rather than lose words."""
    xml = (
        b'<!DOCTYPE article [<!ENTITY co "Company">]>'
        b"<article><body><p>Made by &co; here.</p></body></article>"
    )
    with pytest.raises(JatsParseError, match="unresolved entity reference &co;"):
        parse_jats(xml)


def test_undeclared_entity_with_external_dtd_fails_loudly() -> None:
    """An entity left for an external DTD (never loaded) fails instead of vanishing."""
    xml = (
        b'<!DOCTYPE article PUBLIC "-//NLM//DTD JATS//EN" "JATS.dtd">'
        b"<article><body><p>A&nbsp;B</p></body></article>"
    )
    with pytest.raises(JatsParseError, match="&nbsp;"):
        parse_jats(xml)


def test_predefined_and_character_entities_still_parse() -> None:
    """The five XML entities and numeric character references are ordinary text."""
    xml = b"<article><body><p>a &lt; b &amp;&#160;c &#x3B1;</p></body></article>"
    assert [p.text for p in parse_jats(xml).iter_paragraphs()] == ["a < b & c \u03b1"]


def test_entity_expansion_bomb_is_refused_quickly() -> None:
    """Billion laughs: libxml2's amplification limit refuses the document at once."""
    entities = '<!ENTITY lol "lol">' + "".join(
        f'<!ENTITY lol{i} "{("&lol" + (str(i - 1) if i > 1 else "") + ";") * 10}">'
        for i in range(1, 10)
    )
    xml = f"<!DOCTYPE article [{entities}]><article><body><p>&lol9;</p></body></article>"
    start = time.perf_counter()
    with pytest.raises(JatsParseError, match="amplification"):
        parse_jats(xml.encode())
    assert time.perf_counter() - start < 1.0


def test_external_dtd_is_not_loaded() -> None:
    """A DOCTYPE pointing at an unreachable DTD parses without trying to load it."""
    xml = (
        b'<!DOCTYPE article PUBLIC "-//NLM//DTD JATS//EN" "/nonexistent/path/JATS.dtd">'
        b"<article><body><p>Fine.</p></body></article>"
    )
    assert [p.text for p in parse_jats(xml).iter_paragraphs()] == ["Fine."]


def test_network_dtd_reference_does_not_fetch() -> None:
    """An http DTD URL (as in PLOS files) is neither fetched nor an error."""
    xml = (
        b'<!DOCTYPE article PUBLIC "-//NLM//DTD JATS//EN" '
        b'"http://jats.nlm.nih.gov/publishing/1.3/JATS-journalpublishing1-3.dtd">'
        b"<article><body><p>Offline.</p></body></article>"
    )
    assert [p.text for p in parse_jats(xml).iter_paragraphs()] == ["Offline."]


def test_malformed_xml_raises_instead_of_recovering() -> None:
    """Malformed input fails loudly; silent recovery could drop permissions blocks."""
    with pytest.raises(JatsParseError, match="not well-formed"):
        parse_jats(b"<article><body><p>unclosed</body></article>")


def test_size_limit_is_enforced(tmp_path: Path) -> None:
    """Inputs over the size limit are refused, for bytes and for files."""
    data = b"<article><body><p>" + b"x" * 200 + b"</p></body></article>"
    with pytest.raises(JatsParseError, match="limit"):
        parse_jats(data, max_bytes=100)
    path = tmp_path / "big.xml"
    path.write_bytes(data)
    with pytest.raises(JatsParseError, match="limit"):
        parse_jats_file(path, max_bytes=100)


def test_processing_instructions_and_comments_are_dropped() -> None:
    """Comments and processing instructions never reach the text."""
    xml = b"<article><body><p>A<!-- hidden --><?pi data?>B</p></body></article>"
    assert [p.text for p in parse_jats(xml).iter_paragraphs()] == ["AB"]
