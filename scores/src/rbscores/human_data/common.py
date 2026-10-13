"""Parts shared by the two human-study formats: passages, raters, checks.

Both formats are single UTF-8 JSON documents with a schema name, a version,
a ``synthetic`` flag (true for made-up test data, which must never be
reported as a result), the passages shown, and pseudonymous raters. The
formats are specified in docs/data-formats/.

Privacy: rater IDs are pseudonyms of letters, digits, ``_`` and ``-`` only,
so an e-mail address or a name with spaces cannot be stored by mistake. Keep
the key linking pseudonyms to people (if any) outside this data.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypeGuard

SUPPORTED_VERSION: Final = 1
MAX_FILE_BYTES: Final = 50 * 1024 * 1024
ID_PATTERN: Final = re.compile(r"[A-Za-z0-9_\-]{1,64}")
BACKGROUNDS: Final = (
    "secondary_or_less",
    "university_other_field",
    "university_related_field",
    "postgraduate_related_field",
    "not_reported",
)
"""Allowed rater backgrounds: highest education, relative to the passages' field."""


class HumanDataError(ValueError):
    """Raised when a study file is invalid; lists every problem found.

    Attributes:
        problems: One message per problem.
    """

    def __init__(self, problems: list[str]) -> None:
        """Create the error.

        Args:
            problems: One message per problem (at least one).
        """
        super().__init__(f"{len(problems)} problem(s): " + "; ".join(problems[:5]))
        self.problems = tuple(problems)


@dataclass(frozen=True, slots=True)
class PassageSource:
    """Where a passage came from, so results can be traced and licences checked.

    Attributes:
        doi: The paper's DOI, if any.
        paragraph_id: The rbcore paragraph ID, if the passage is one paragraph.
        licence: The passage's licence (SPDX-style, e.g. "CC-BY-4.0").
    """

    doi: str | None = None
    paragraph_id: str | None = None
    licence: str | None = None


@dataclass(frozen=True, slots=True)
class Passage:
    """A text shown to raters.

    Attributes:
        passage_id: Unique ID within the study.
        text: The exact text shown; mark offsets index into it.
        source: Provenance, if recorded.
    """

    passage_id: str
    text: str
    source: PassageSource | None = None


@dataclass(frozen=True, slots=True)
class Rater:
    """A pseudonymous rater.

    Attributes:
        rater_id: Pseudonym (letters, digits, ``_``, ``-``).
        background: One of :data:`BACKGROUNDS`.
    """

    rater_id: str
    background: str = "not_reported"


@dataclass(frozen=True, slots=True)
class StudyHeader:
    """Fields every study file has.

    Attributes:
        study_id: Study identifier.
        synthetic: True for made-up data (tests and demos only).
        description: What the study is.
        passages: Passages by ID, in file order.
        raters: Raters by ID, in file order.
    """

    study_id: str
    synthetic: bool
    description: str
    passages: Mapping[str, Passage]
    raters: Mapping[str, Rater]


def read_json(path: str | Path) -> Any:
    """Read a JSON file, refusing very large ones.

    Args:
        path: File path.

    Returns:
        The parsed JSON.

    Raises:
        HumanDataError: If the file is too large or not valid JSON.
    """
    file_path = Path(path)
    if file_path.stat().st_size > MAX_FILE_BYTES:
        raise HumanDataError([f"{file_path} is larger than {MAX_FILE_BYTES} bytes"])
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HumanDataError([f"{file_path} is not valid UTF-8 JSON: {exc}"]) from exc


def parse_header(data: Any, schema: str, problems: list[str]) -> StudyHeader | None:
    """Check and parse the fields shared by both formats.

    Problems are appended to ``problems`` rather than raised, so a file's
    every problem is reported at once.

    Args:
        data: Parsed JSON.
        schema: Expected ``schema`` value.
        problems: List to append problems to.

    Returns:
        The header, or None if the document is not even an object.
    """
    if not isinstance(data, dict):
        problems.append("the document must be a JSON object")
        return None

    # Schema, version and the synthetic flag.
    if data.get("schema") != schema:
        problems.append(f"'schema' must be {schema!r}")
    if data.get("version") != SUPPORTED_VERSION:
        problems.append(f"'version' must be {SUPPORTED_VERSION}")
    synthetic = data.get("synthetic")
    if not isinstance(synthetic, bool):
        problems.append("'synthetic' must be true or false")
    study_id = data.get("study_id")
    if not isinstance(study_id, str) or not study_id.strip():
        problems.append("'study_id' must be a non-empty string")
    description = data.get("description", "")
    if not isinstance(description, str):
        problems.append("'description' must be a string")
        description = ""

    return StudyHeader(
        study_id=study_id if isinstance(study_id, str) else "",
        synthetic=bool(synthetic),
        description=description,
        passages=_parse_passages(data.get("passages"), problems),
        raters=_parse_raters(data.get("raters"), problems),
    )


def _parse_passages(items: Any, problems: list[str]) -> dict[str, Passage]:
    """Parse the ``passages`` list.

    Args:
        items: The raw value.
        problems: List to append problems to.

    Returns:
        Valid passages by ID.
    """
    # The list itself must exist and hold objects.
    passages: dict[str, Passage] = {}
    if not isinstance(items, list) or not items:
        problems.append("'passages' must be a non-empty list")
        return passages
    for index, item in enumerate(items):
        where = f"passages[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue

        # Each passage needs a valid, unique ID and some text; problems skip it.
        passage_id = item.get("passage_id")
        text = item.get("text")
        if not valid_id(passage_id):
            problems.append(f"{where}.passage_id must match {ID_PATTERN.pattern}")
            continue
        if not isinstance(text, str) or not text.strip():
            problems.append(f"{where}.text must be a non-empty string")
            continue
        if passage_id in passages:
            problems.append(f"{where}.passage_id {passage_id!r} is duplicated")
            continue

        # The optional source reports its own problems without dropping the passage.
        passages[passage_id] = Passage(
            passage_id, text, _parse_source(item.get("source"), where, problems)
        )
    return passages


def _parse_source(raw: Any, where: str, problems: list[str]) -> PassageSource | None:
    """Parse an optional passage ``source`` object.

    Args:
        raw: The raw value.
        where: Location for messages.
        problems: List to append problems to.

    Returns:
        The source, or None if absent or invalid.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        problems.append(f"{where}.source must be an object")
        return None
    fields = {}
    for name in ("doi", "paragraph_id", "licence"):
        value = raw.get(name)
        if value is not None and not isinstance(value, str):
            problems.append(f"{where}.source.{name} must be a string")
            value = None
        fields[name] = value
    return PassageSource(**fields)


def _parse_raters(items: Any, problems: list[str]) -> dict[str, Rater]:
    """Parse the ``raters`` list.

    Args:
        items: The raw value.
        problems: List to append problems to.

    Returns:
        Valid raters by ID.
    """
    # The list itself must exist and hold objects.
    raters: dict[str, Rater] = {}
    if not isinstance(items, list) or not items:
        problems.append("'raters' must be a non-empty list")
        return raters
    for index, item in enumerate(items):
        where = f"raters[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where} must be an object")
            continue

        # A pseudonymous, unique ID and a known background; problems skip the rater.
        rater_id = item.get("rater_id")
        background = item.get("background", "not_reported")
        if not valid_id(rater_id):
            problems.append(
                f"{where}.rater_id must be a pseudonym matching {ID_PATTERN.pattern} "
                "(never a name or e-mail address)"
            )
            continue
        if background not in BACKGROUNDS:
            problems.append(f"{where}.background must be one of {', '.join(BACKGROUNDS)}")
            continue
        if rater_id in raters:
            problems.append(f"{where}.rater_id {rater_id!r} is duplicated")
            continue
        raters[rater_id] = Rater(rater_id, background)
    return raters


def valid_id(value: Any) -> TypeGuard[str]:
    """Check an identifier against :data:`ID_PATTERN`.

    Args:
        value: Candidate identifier.

    Returns:
        True if it is a string of 1-64 letters, digits, ``_`` or ``-``.
    """
    return isinstance(value, str) and ID_PATTERN.fullmatch(value) is not None
