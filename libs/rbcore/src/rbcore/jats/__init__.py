"""Safe JATS XML parsing into typed, immutable dataclasses.

Example::

    from rbcore.jats import parse_jats_file

    article = parse_jats_file("PMC10718527.xml")
    for paragraph in article.iter_paragraphs():
        print(paragraph.id, paragraph.text)
"""

from rbcore.jats.model import (
    Article,
    Author,
    Figure,
    Funding,
    FundingAward,
    Identifiers,
    Journal,
    Paragraph,
    PublicationDate,
    Section,
)
from rbcore.jats.parser import JatsParseError, parse_jats, parse_jats_file, parse_permissions

__all__ = [
    "Article",
    "Author",
    "Figure",
    "Funding",
    "FundingAward",
    "Identifiers",
    "JatsParseError",
    "Journal",
    "Paragraph",
    "PublicationDate",
    "Section",
    "parse_jats",
    "parse_jats_file",
    "parse_permissions",
]
