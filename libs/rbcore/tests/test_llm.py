"""Tests for rbcore.llm. No test here calls a real API; the SDK is replaced by a stub."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from rbcore.config import ConfigError, Settings
from rbcore.llm import (
    FAKE_MODEL,
    AnthropicClient,
    FakeLLMClient,
    LLMClient,
    LLMError,
    LLMRefusalError,
    LLMRequest,
    Message,
    request_fingerprint,
)


def test_fake_is_deterministic_and_labelled_synthetic() -> None:
    """The same request always yields the same, obviously synthetic, reply."""
    client = FakeLLMClient()
    request = LLMRequest.from_prompt("Explain p-values.", system="Be plain.", prompt_version="v1")
    first, second = client.complete(request), client.complete(request)
    assert first == second
    assert first.synthetic
    assert first.text.startswith("[SYNTHETIC FAKE LLM OUTPUT ")
    assert first.model == FAKE_MODEL
    assert first.prompt_version == "v1"
    assert client.calls == [request, request]


def test_fake_differs_for_different_requests() -> None:
    """Different prompts give different fingerprints and replies."""
    client = FakeLLMClient()
    a = client.complete(LLMRequest.from_prompt("A"))
    b = client.complete(LLMRequest.from_prompt("B"))
    assert a.text != b.text
    assert request_fingerprint(LLMRequest.from_prompt("A")) != request_fingerprint(
        LLMRequest.from_prompt("B")
    )


def test_fake_custom_responder_and_token_counts() -> None:
    """A responder controls the text; token counts are whitespace-based."""
    client = FakeLLMClient(responder=lambda request: "one two three")
    response = client.complete(LLMRequest.from_prompt("four five", system="six"))
    assert response.text == "one two three"
    assert (response.input_tokens, response.output_tokens) == (3, 3)


def test_fake_satisfies_the_protocol() -> None:
    """FakeLLMClient and AnthropicClient are both LLMClients."""
    assert isinstance(FakeLLMClient(), LLMClient)
    assert isinstance(AnthropicClient("model-x", sdk_client=_StubSDK()), LLMClient)


# ----- AnthropicClient with a stub SDK -------------------------------------


@dataclass
class _Block:
    """Stub content block."""

    type: str
    text: str = ""


@dataclass
class _Usage:
    """Stub usage object."""

    input_tokens: int = 11
    output_tokens: int = 7


@dataclass
class _Message:
    """Stub Messages API response."""

    content: list[_Block]
    model: str = "model-x"
    stop_reason: str = "end_turn"
    usage: _Usage = field(default_factory=_Usage)


class _StubMessages:
    """Stub ``client.messages`` that records calls and returns a canned message."""

    def __init__(self, reply: _Message | Exception) -> None:
        """Store the canned reply (or exception to raise)."""
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Message:
        """Record the call and return or raise the canned reply."""
        self.calls.append(kwargs)
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


class _StubSDK:
    """Stub of ``anthropic.Anthropic`` exposing only ``messages``."""

    def __init__(self, reply: _Message | Exception | None = None) -> None:
        """Create the stub with a canned reply."""
        self.messages = _StubMessages(
            reply if reply is not None else _Message([_Block("text", "ok")])
        )


def test_anthropic_client_maps_request_and_response() -> None:
    """Only set fields are sent; text blocks are joined; usage and model are reported."""
    sdk = _StubSDK(
        _Message([_Block("thinking"), _Block("text", "Hello "), _Block("text", "world")])
    )
    client = AnthropicClient("model-x", sdk_client=sdk)
    request = LLMRequest(
        messages=(Message("user", "Hi"), Message("assistant", "Hey"), Message("user", "Again")),
        system="sys",
        max_tokens=100,
        prompt_version="p2",
    )
    response = client.complete(request)
    (call,) = sdk.messages.calls
    assert call == {
        "model": "model-x",
        "max_tokens": 100,
        "messages": [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hey"},
            {"role": "user", "content": "Again"},
        ],
        "system": "sys",
    }
    assert "temperature" not in call  # never sent unless explicitly requested
    assert response.text == "Hello world"
    assert (response.model, response.input_tokens, response.output_tokens) == ("model-x", 11, 7)
    assert response.prompt_version == "p2"
    assert not response.synthetic


def test_anthropic_client_sends_temperature_only_when_set() -> None:
    """An explicit temperature is passed through."""
    sdk = _StubSDK()
    AnthropicClient("model-x", sdk_client=sdk).complete(
        LLMRequest.from_prompt("x", temperature=0.0)
    )
    assert sdk.messages.calls[0]["temperature"] == 0.0


def test_anthropic_client_raises_on_refusal() -> None:
    """stop_reason == "refusal" raises LLMRefusalError rather than returning text."""
    sdk = _StubSDK(_Message([], stop_reason="refusal"))
    with pytest.raises(LLMRefusalError):
        AnthropicClient("model-x", sdk_client=sdk).complete(LLMRequest.from_prompt("x"))


def test_anthropic_sdk_errors_become_llm_errors() -> None:
    """Errors raised by the anthropic package are wrapped in LLMError."""
    import anthropic

    sdk = _StubSDK(anthropic.AnthropicError("boom"))
    with pytest.raises(LLMError, match="boom"):
        AnthropicClient("model-x", sdk_client=sdk).complete(LLMRequest.from_prompt("x"))


def test_non_sdk_errors_propagate_unchanged() -> None:
    """Programming errors are not disguised as API failures."""
    sdk = _StubSDK(ValueError("bug"))
    with pytest.raises(ValueError, match="bug"):
        AnthropicClient("model-x", sdk_client=sdk).complete(LLMRequest.from_prompt("x"))


def test_anthropic_client_requires_model_and_key() -> None:
    """No model or no key: construction fails before any network use."""
    with pytest.raises(LLMError, match="model ID"):
        AnthropicClient("", sdk_client=_StubSDK())
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        AnthropicClient("model-x")


def test_from_settings_requires_configuration() -> None:
    """from_settings reads the model and key from Settings, failing clearly when unset."""
    with pytest.raises(ConfigError, match="RB_LLM_GENERATION_MODEL"):
        AnthropicClient.from_settings(Settings.from_env({"ANTHROPIC_API_KEY": "k"}))
    with pytest.raises(ConfigError, match="ANTHROPIC_API_KEY"):
        AnthropicClient.from_settings(Settings.from_env({"RB_LLM_GENERATION_MODEL": "m"}))


def test_from_settings_builds_client_without_calling_api() -> None:
    """With a (dummy) key and model set, construction succeeds and makes no request."""
    client = AnthropicClient.from_settings(
        Settings.from_env({"ANTHROPIC_API_KEY": "dummy-not-a-key", "RB_LLM_GENERATION_MODEL": "m"})
    )
    assert client.model == "m"
