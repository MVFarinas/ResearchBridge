"""Versioned prompt files.

A prompt lives in ``benchmark/prompts/<version>.md`` and is never edited once a
run has used it: a change means a new version file (``rewrite_v2.md``), so
every output can be traced to the exact text that produced it. Provenance
records both the version and the SHA-256 of the file.

File format::

    ---
    version: rewrite_v1
    purpose: one line
    max_tokens: 8000
    ---
    ## System
    ...system prompt...
    ## User
    ...user prompt template with {{placeholders}}...

Placeholders are ``{{name}}``. Rendering fails if a placeholder has no value
or a value has no placeholder, so a template and its caller cannot drift
apart silently.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rbbench.paths import PROMPTS_DIR

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_][a-z0-9_]*)\s*\}\}")
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_SYSTEM_HEADING = "## System"
_USER_HEADING = "## User"


class PromptError(ValueError):
    """Raised when a prompt file is malformed or rendered with the wrong values."""


@dataclass(frozen=True, slots=True)
class PromptTemplate:
    """A loaded, versioned prompt.

    Attributes:
        version: The prompt version, e.g. "rewrite_v1" (equals the file stem).
        system: The system prompt (may itself contain placeholders).
        user: The user-turn template.
        max_tokens: Output token ceiling for requests built from this prompt.
        sha256: SHA-256 of the whole file, for provenance.
        purpose: One-line description from the front matter.
    """

    version: str
    system: str
    user: str
    max_tokens: int
    sha256: str
    purpose: str = ""

    @property
    def placeholders(self) -> frozenset[str]:
        """Every placeholder name used in the system prompt or user template."""
        return frozenset(_PLACEHOLDER.findall(self.system) + _PLACEHOLDER.findall(self.user))

    def render(self, **values: str) -> tuple[str, str]:
        """Fill the placeholders.

        Args:
            **values: One string per placeholder.

        Returns:
            ``(system, user)`` with every placeholder replaced.

        Raises:
            PromptError: If a placeholder has no value or a value is unused.
        """
        missing = self.placeholders - values.keys()
        unused = values.keys() - self.placeholders
        if missing or unused:
            raise PromptError(
                f"{self.version}: missing values {sorted(missing)}, unused values {sorted(unused)}"
            )

        def substitute(template: str) -> str:
            """Replace every placeholder in one template."""
            return _PLACEHOLDER.sub(lambda match: values[match.group(1)], template)

        return substitute(self.system), substitute(self.user)


def parse_prompt(text: str, *, expected_version: str | None = None) -> PromptTemplate:
    """Parse the text of a prompt file.

    Args:
        text: File content.
        expected_version: If given, the front matter's ``version`` must match.

    Returns:
        The template.

    Raises:
        PromptError: If the front matter or the two sections are missing or
            invalid.
    """
    # Front matter carries the version and request settings.
    match = _FRONT_MATTER.match(text)
    if match is None:
        raise PromptError("prompt file must start with a '---' front matter block")
    meta: Any = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict) or not isinstance(meta.get("version"), str):
        raise PromptError("front matter must be a mapping with a string 'version'")
    version = meta["version"]
    if expected_version is not None and version != expected_version:
        raise PromptError(f"file declares version {version!r}, expected {expected_version!r}")
    max_tokens = meta.get("max_tokens", 4096)
    if not isinstance(max_tokens, int) or max_tokens <= 0:
        raise PromptError("max_tokens must be a positive integer")

    # The body has exactly one system section followed by one user section.
    body = text[match.end() :]
    lines = body.splitlines()
    if lines.count(_SYSTEM_HEADING) != 1 or lines.count(_USER_HEADING) != 1:
        raise PromptError("prompt body needs exactly one '## System' and one '## User' heading")
    system_at, user_at = lines.index(_SYSTEM_HEADING), lines.index(_USER_HEADING)
    if not system_at < user_at:
        raise PromptError("'## System' must come before '## User'")
    system = "\n".join(lines[system_at + 1 : user_at]).strip()
    user = "\n".join(lines[user_at + 1 :]).strip()
    if not system or not user:
        raise PromptError("system and user sections must not be empty")

    return PromptTemplate(
        version=version,
        system=system,
        user=user,
        max_tokens=max_tokens,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        purpose=str(meta.get("purpose", "")),
    )


def load_prompt(version: str, prompts_dir: Path = PROMPTS_DIR) -> PromptTemplate:
    """Load ``<prompts_dir>/<version>.md``.

    Args:
        version: Prompt version, e.g. "rewrite_v1".
        prompts_dir: Directory holding prompt files.

    Returns:
        The template.

    Raises:
        PromptError: If the file is malformed or declares another version.
        FileNotFoundError: If there is no such prompt file.
    """
    path = prompts_dir / f"{version}.md"
    return parse_prompt(path.read_text(encoding="utf-8"), expected_version=version)
