"""Flatten JATS inline markup into clean, readable plain text.

Rules:

* Inline formatting (italic, bold, sc, named-content, ext-link, ...) keeps its
  text and loses its markup.
* Cross-references (``xref``) keep their visible text, so "[1, 2]" and
  "Pandey et al., 2015" stay readable. A superscript holding citations becomes
  "[...]"; any other superscript becomes "^..." so "10^5" is not read as "105".
* Formulas use their TeX source when present, else the MathML ``@alttext``,
  else the flattened MathML text.
* Floating objects (figures, tables, graphics, media) are skipped: they are
  extracted separately with their own captions and permissions.
* For ``alternatives`` only the first rendering is used, to avoid duplicates.
* Whitespace (including no-break spaces) collapses to single spaces.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from lxml import etree

# Floating or non-textual objects whose content never belongs in running text.
SKIPPED = frozenset(
    {
        "fig",
        "fig-group",
        "table-wrap",
        "table-wrap-group",
        "graphic",
        "inline-graphic",
        "media",
        "supplementary-material",
        "alt-text",
        "long-desc",
        "object-id",
        "institution-id",
    }
)

# Elements that start a new block when they appear inside flattened content;
# padding them with spaces keeps adjacent words from running together.
_BLOCKISH = frozenset(
    {
        "p",
        "list",
        "list-item",
        "title",
        "label",
        "caption",
        "disp-quote",
        "def-list",
        "def-item",
        "term",
        "def",
        "fn",
        "sec",
        "license-p",
        "td",
        "th",
        "tr",
    }
)

_WHITESPACE = re.compile(r"\s+")


def local_name(element: etree._Element) -> str:
    """Return an element's tag without any namespace, or "" for non-elements.

    Args:
        element: An lxml node (elements, or entity references left in place
            by the safe parser).

    Returns:
        The local tag name, e.g. "license_ref" for ``ali:license_ref``.
    """
    if isinstance(element, etree._Entity):
        return ""
    return etree.QName(element).localname


def normalise_whitespace(text: str) -> str:
    """Collapse whitespace runs to single spaces and strip the ends.

    Args:
        text: Any text.

    Returns:
        The normalised text.
    """
    return _WHITESPACE.sub(" ", text).strip()


def flatten(element: etree._Element, *, skip: Iterable[str] = ()) -> str:
    """Flatten an element's content to normalised plain text.

    The element's own tail is not included.

    Args:
        element: The element to flatten.
        skip: Extra local names to omit (with their content), e.g. "label".

    Returns:
        Plain text, possibly empty.
    """
    parts: list[str] = []
    _collect(element, parts, SKIPPED | frozenset(skip))
    return normalise_whitespace("".join(parts))


def _collect(element: etree._Element, parts: list[str], skipped: frozenset[str]) -> None:
    """Append the text of ``element``'s content to ``parts``, recursively.

    Args:
        element: The element whose text and children are collected.
        parts: Output buffer.
        skipped: Local names whose content is omitted.
    """
    if element.text:
        parts.append(element.text)
    for child in element:
        name = local_name(child)
        if name and name not in skipped:
            _collect_child(child, name, parts, skipped)
        # Tail text belongs to the parent, so it survives even a skipped child.
        if child.tail:
            parts.append(child.tail)


def _collect_child(
    child: etree._Element, name: str, parts: list[str], skipped: frozenset[str]
) -> None:
    """Append the text of one child element, applying the special cases.

    Args:
        child: The child element.
        name: Its local name.
        parts: Output buffer.
        skipped: Local names whose content is omitted.
    """
    # Formulas read as their TeX or alt text; display formulas are set apart.
    if name in {"inline-formula", "disp-formula"}:
        parts.append(f" {formula_text(child)} " if name == "disp-formula" else formula_text(child))
    elif name == "alternatives":
        # Alternative renderings of one thing: take the first textual one.
        first = next((c for c in child if local_name(c) and local_name(c) not in skipped), None)
        if first is not None:
            _collect_child(first, local_name(first), parts, skipped)
    elif name == "sup":
        # Citations in superscript read as [..]; any other superscript as ^..
        # so that 10^5 is not read as 105.
        inner = flatten(child, skip=skipped)
        if inner:
            parts.append(f"[{inner}]" if _contains_citation(child) else f"^{inner}")
    elif name == "break":
        # A line break separates words just like a space.
        parts.append(" ")
    elif name in _BLOCKISH:
        # Pad block-level content so adjacent blocks' words do not run together.
        parts.append(" ")
        _collect(child, parts, skipped)
        parts.append(" ")
    else:
        # Any other inline element keeps its text and loses its markup.
        _collect(child, parts, skipped)


def _contains_citation(element: etree._Element) -> bool:
    """Whether an element contains a bibliographic cross-reference.

    Args:
        element: The element to search.

    Returns:
        True if any descendant is an ``xref`` with ``ref-type="bibr"``.
    """
    return any(
        local_name(node) == "xref" and node.get("ref-type") == "bibr"
        for node in element.iterdescendants()
    )


def formula_text(element: etree._Element) -> str:
    """Return the readable text of a formula element.

    Args:
        element: An ``inline-formula`` or ``disp-formula`` (or any element
            containing ``tex-math`` or MathML).

    Returns:
        TeX source if present, else MathML ``@alttext``, else the flattened
        MathML text; labels such as "(1)" are omitted.
    """
    for node in element.iter():
        if local_name(node) == "tex-math":
            return normalise_whitespace("".join(node.itertext()))
    for node in element.iter():
        if local_name(node) == "math" and node.get("alttext"):
            return normalise_whitespace(node.get("alttext", ""))
    return flatten(element, skip={"label"})
