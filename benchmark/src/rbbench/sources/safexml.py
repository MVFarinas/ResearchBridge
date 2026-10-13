"""Hardened XML parsing for small non-JATS documents (such as S3 bucket listings).

JATS goes through :mod:`rbcore.jats`. Anything else downloaded is parsed here
with the same hardening: no entity resolution, no DTD loading, no network
access, and huge-tree support off. Recovery mode stays off so malformed input
fails loudly instead of being silently repaired.
"""

from __future__ import annotations

from lxml import etree

MAX_BYTES = 5 * 1024 * 1024


class UnsafeXmlError(ValueError):
    """Raised when XML is malformed, oversized or declares a DTD."""


def parse_untrusted_xml(data: bytes, *, max_bytes: int = MAX_BYTES) -> etree._Element:
    """Parse untrusted XML safely.

    Args:
        data: The document bytes.
        max_bytes: Refuse larger documents.

    Returns:
        The root element.

    Raises:
        UnsafeXmlError: If the document is too large, malformed, or declares a
            DOCTYPE (which none of the documents parsed here legitimately need).
    """
    if len(data) > max_bytes:
        raise UnsafeXmlError(f"XML document of {len(data)} bytes exceeds {max_bytes}")
    parser = etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
        recover=False,
    )
    try:
        root = etree.fromstring(data, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise UnsafeXmlError(f"malformed XML: {exc}") from exc
    # A listing never needs a DTD; one is a sign of something unexpected.
    if root.getroottree().docinfo.doctype:
        raise UnsafeXmlError("XML with a DOCTYPE declaration is refused")
    return root
