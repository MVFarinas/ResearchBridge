"""Settings read from the environment.

Model IDs and keys live in configuration, never in code (decisions.md §1.6).
Every key is optional: code must degrade gracefully when one is missing, and
anything that truly needs a value asks for it through a ``require_*`` method,
which raises :class:`ConfigError` with a message naming the variable.

The process environment is the only source. To use a local ``.env`` file,
export it into the shell first (``set -a; source .env; set +a``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_USER_AGENT = "ResearchBridge-dev/0.1 (+https://github.com/MVFarinas/ResearchBridge)"
DEFAULT_DB_PORT = 5433


class ConfigError(RuntimeError):
    """Raised when a required setting is missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings.

    Attributes:
        anthropic_api_key: ``ANTHROPIC_API_KEY``; hidden from repr.
        generation_model: ``RB_LLM_GENERATION_MODEL``, the model that writes
            rewrites and annotations (chosen by the Phase 1 benchmark).
        judge_model: ``RB_LLM_JUDGE_MODEL``, the faithfulness judge; must
            differ from the generation model (decisions.md §1.4).
        openalex_api_key: ``OPENALEX_API_KEY``; hidden from repr.
        ncbi_api_key: ``NCBI_API_KEY``; hidden from repr.
        data_dir: ``RB_DATA_DIR`` (default ``data``), for downloads and caches.
        db_port: ``RB_DB_PORT`` (default 5433), the local Postgres host port.
        user_agent: HTTP User-Agent; never contains personal identifiers.
    """

    anthropic_api_key: str | None = field(default=None, repr=False)
    generation_model: str | None = None
    judge_model: str | None = None
    openalex_api_key: str | None = field(default=None, repr=False)
    ncbi_api_key: str | None = field(default=None, repr=False)
    data_dir: Path = Path("data")
    db_port: int = DEFAULT_DB_PORT
    user_agent: str = DEFAULT_USER_AGENT

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Settings:
        """Build settings from environment variables.

        Empty values count as unset, so a copied ``.env.example`` with blank
        keys behaves like no keys at all.

        Args:
            environ: Mapping to read (defaults to ``os.environ``).

        Returns:
            The settings.

        Raises:
            ConfigError: If ``RB_DB_PORT`` is not a valid port number.
        """
        env = os.environ if environ is None else environ

        def get(name: str) -> str | None:
            """Return a stripped variable, or None if unset or blank."""
            value = env.get(name, "").strip()
            return value or None

        port_text = get("RB_DB_PORT")
        try:
            db_port = int(port_text) if port_text else DEFAULT_DB_PORT
        except ValueError as exc:
            raise ConfigError(f"RB_DB_PORT must be an integer, got {port_text!r}") from exc
        if not 0 < db_port < 65536:
            raise ConfigError(f"RB_DB_PORT must be between 1 and 65535, got {db_port}")

        return cls(
            anthropic_api_key=get("ANTHROPIC_API_KEY"),
            generation_model=get("RB_LLM_GENERATION_MODEL"),
            judge_model=get("RB_LLM_JUDGE_MODEL"),
            openalex_api_key=get("OPENALEX_API_KEY"),
            ncbi_api_key=get("NCBI_API_KEY"),
            data_dir=Path(get("RB_DATA_DIR") or "data"),
            db_port=db_port,
        )

    def require_anthropic_api_key(self) -> str:
        """Return the Anthropic API key.

        Returns:
            The key.

        Raises:
            ConfigError: If ``ANTHROPIC_API_KEY`` is unset.
        """
        if not self.anthropic_api_key:
            raise ConfigError(
                "ANTHROPIC_API_KEY is not set; use rbcore.llm.FakeLLMClient for tests and dry runs"
            )
        return self.anthropic_api_key

    def require_model(self, role: str) -> str:
        """Return the configured model ID for a role.

        Args:
            role: "generation" or "judge".

        Returns:
            The model ID.

        Raises:
            ConfigError: If the role is unknown, its model is unset, or the
                judge would be the same model as the generator.
        """
        if role not in {"generation", "judge"}:
            raise ConfigError(f"unknown model role {role!r}; expected 'generation' or 'judge'")
        model = self.generation_model if role == "generation" else self.judge_model
        if not model:
            raise ConfigError(f"RB_LLM_{role.upper()}_MODEL is not set")
        # decisions.md §1.4: the judge must not be the model that generated the text.
        if role == "judge" and model == self.generation_model:
            raise ConfigError("RB_LLM_JUDGE_MODEL must differ from RB_LLM_GENERATION_MODEL")
        return model
