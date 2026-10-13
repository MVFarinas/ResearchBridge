"""Building the LLM client for a benchmark step.

Every step takes an :class:`rbcore.llm.LLMClient`. Two kinds exist:

* ``fake``: :class:`rbcore.llm.FakeLLMClient` with the benchmark's synthetic
  responder (:mod:`rbbench.fakes`). Deterministic, offline, and every output
  is labelled synthetic. Used by tests and the dry run.
* ``anthropic``: :class:`rbcore.llm.AnthropicClient` (official SDK, imported
  lazily; key from ``ANTHROPIC_API_KEY``; model ID from configuration). It
  costs money, so it is only built when the caller passes ``live=True``
  (the CLI's ``--live`` flag) on top of having a key.
"""

from __future__ import annotations

from enum import StrEnum

from rbbench.fakes import synthetic_responder
from rbcore.config import Settings
from rbcore.llm import AnthropicClient, FakeLLMClient, LLMClient


class ClientKind(StrEnum):
    """Which client to build."""

    FAKE = "fake"
    ANTHROPIC = "anthropic"


class LiveCallsNotAllowedError(RuntimeError):
    """Raised when a real client is requested without explicit permission."""


def make_client(
    kind: ClientKind,
    *,
    role: str,
    settings: Settings,
    live: bool = False,
    model: str | None = None,
) -> tuple[LLMClient, str]:
    """Build a client for one role.

    Args:
        kind: Fake or real.
        role: "generation" (rewrite, decomposition) or "judge".
        settings: Runtime settings (key and model IDs from the environment).
        live: Must be True to build the real client; guards against
            accidental paid calls.
        model: Model ID override for the real client (still configuration,
            never code); defaults to the role's configured model.

    Returns:
        ``(client, requested_model)``; the fake reports its own model name.

    Raises:
        LiveCallsNotAllowedError: For the real client without ``live``.
        rbcore.config.ConfigError: If the key or the role's model is unset,
            or the judge would be the generation model.
    """
    if kind is ClientKind.FAKE:
        client = FakeLLMClient(synthetic_responder)
        return client, "fake-deterministic"
    if not live:
        raise LiveCallsNotAllowedError(
            "real LLM calls cost money; pass --live (live=True) to allow them"
        )
    # Model IDs come from configuration; the judge check lives in Settings.
    requested = model or settings.require_model(role)
    if role == "judge" and requested == settings.generation_model:
        raise LiveCallsNotAllowedError("the judge model must differ from the generation model")
    return AnthropicClient(requested, api_key=settings.require_anthropic_api_key()), requested
