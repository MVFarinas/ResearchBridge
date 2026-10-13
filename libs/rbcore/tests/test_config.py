"""Tests for rbcore.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from rbcore.config import DEFAULT_USER_AGENT, ConfigError, Settings


def test_defaults_without_any_environment() -> None:
    """With nothing set, every key is None and defaults apply."""
    settings = Settings.from_env({})
    assert settings.anthropic_api_key is None
    assert settings.generation_model is None
    assert settings.data_dir == Path("data")
    assert settings.db_port == 5433
    assert settings.user_agent == DEFAULT_USER_AGENT


def test_reads_variables_and_treats_blank_as_unset() -> None:
    """Values are stripped; blank values (as in .env.example) count as unset."""
    settings = Settings.from_env(
        {
            "ANTHROPIC_API_KEY": "   ",
            "RB_LLM_GENERATION_MODEL": " model-a ",
            "RB_LLM_JUDGE_MODEL": "model-b",
            "OPENALEX_API_KEY": "oa-key",
            "RB_DATA_DIR": "custom-data",
            "RB_DB_PORT": "5439",
        }
    )
    assert settings.anthropic_api_key is None
    assert settings.generation_model == "model-a"
    assert settings.openalex_api_key == "oa-key"
    assert settings.data_dir == Path("custom-data")
    assert settings.db_port == 5439


def test_secrets_are_hidden_from_repr() -> None:
    """API keys never appear in logs via repr()."""
    settings = Settings.from_env({"ANTHROPIC_API_KEY": "sk-secret", "NCBI_API_KEY": "ncbi-secret"})
    assert "sk-secret" not in repr(settings)
    assert "ncbi-secret" not in repr(settings)


def test_user_agent_has_no_personal_identifier() -> None:
    """The default User-Agent names the project, with no email or mailto."""
    assert "@" not in DEFAULT_USER_AGENT
    assert "mailto" not in DEFAULT_USER_AGENT.lower()
    assert DEFAULT_USER_AGENT.startswith("ResearchBridge-dev/")


@pytest.mark.parametrize("port", ["abc", "0", "70000"])
def test_invalid_port_is_rejected(port: str) -> None:
    """A non-numeric or out-of-range RB_DB_PORT raises ConfigError."""
    with pytest.raises(ConfigError, match="RB_DB_PORT"):
        Settings.from_env({"RB_DB_PORT": port})


def test_require_methods_name_the_missing_variable() -> None:
    """require_* raise ConfigError naming the variable to set."""
    settings = Settings.from_env({})
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        settings.require_anthropic_api_key()
    with pytest.raises(ConfigError, match="RB_LLM_GENERATION_MODEL"):
        settings.require_model("generation")
    with pytest.raises(ConfigError, match="unknown model role"):
        settings.require_model("rewriter")


def test_judge_must_differ_from_generator() -> None:
    """decisions.md §1.4: the judge is never the generating model."""
    same = Settings.from_env({"RB_LLM_GENERATION_MODEL": "m", "RB_LLM_JUDGE_MODEL": "m"})
    with pytest.raises(ConfigError, match="must differ"):
        same.require_model("judge")
    different = Settings.from_env({"RB_LLM_GENERATION_MODEL": "m", "RB_LLM_JUDGE_MODEL": "j"})
    assert different.require_model("judge") == "j"
    assert different.require_model("generation") == "m"
