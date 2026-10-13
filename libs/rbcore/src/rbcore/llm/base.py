"""The small interface every LLM-dependent component codes against.

Production code receives an :class:`LLMClient` and never constructs a vendor
SDK itself, so tests and dry runs can pass :class:`rbcore.llm.FakeLLMClient`
and no code path needs an API key to run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Raised when an LLM call fails or returns an unusable response."""


class LLMRefusalError(LLMError):
    """Raised when the model declines the request (``stop_reason == "refusal"``)."""


@dataclass(frozen=True, slots=True)
class Message:
    """One conversation turn.

    Attributes:
        role: "user" or "assistant".
        content: The turn's text.
    """

    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True, slots=True)
class LLMRequest:
    """A text-in, text-out request.

    Attributes:
        messages: Conversation turns, starting with a user turn.
        system: Optional system prompt.
        max_tokens: Output token ceiling.
        temperature: Sampling temperature, or None to use the model default.
            Some current Claude models reject non-default sampling values, so
            leave this None unless the experiment needs it.
        prompt_version: Caller's prompt version, recorded for provenance
            (decisions.md §1.3) and echoed on the response.
    """

    messages: tuple[Message, ...]
    system: str | None = None
    max_tokens: int = 4096
    temperature: float | None = None
    prompt_version: str | None = None

    @classmethod
    def from_prompt(
        cls,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float | None = None,
        prompt_version: str | None = None,
    ) -> LLMRequest:
        """Build a single-turn request.

        Args:
            prompt: The user message.
            system: Optional system prompt.
            max_tokens: Output token ceiling.
            temperature: Sampling temperature, or None for the model default.
            prompt_version: Caller's prompt version, for provenance.

        Returns:
            The request.
        """
        return cls(
            messages=(Message("user", prompt),),
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            prompt_version=prompt_version,
        )


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """The model's reply plus what provenance needs.

    Attributes:
        text: Concatenated text output.
        model: The model that actually answered (as reported by the API).
        stop_reason: Why generation stopped (e.g. "end_turn", "max_tokens").
        input_tokens: Prompt tokens billed.
        output_tokens: Output tokens billed.
        prompt_version: Echo of the request's ``prompt_version``.
        synthetic: True when produced by a fake client, never a real model.
    """

    text: str
    model: str
    stop_reason: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    prompt_version: str | None = None
    synthetic: bool = field(default=False)


@runtime_checkable
class LLMClient(Protocol):
    """Anything that can answer an :class:`LLMRequest`."""

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send one request and return the reply.

        Args:
            request: The request.

        Returns:
            The response.

        Raises:
            LLMError: On failure.
        """
        ...
