"""The real Claude client, behind the :class:`rbcore.llm.LLMClient` interface.

Uses the official ``anthropic`` SDK (install ``researchbridge-rbcore[anthropic]``).
The key comes from ``ANTHROPIC_API_KEY`` and the model ID from configuration
(:class:`rbcore.config.Settings`), never from code. Constructing the client
does not call the API; only :meth:`AnthropicClient.complete` does.

Refusals (``stop_reason == "refusal"``) raise :class:`LLMRefusalError`. No
server-side model fallback is enabled: the Phase 1 benchmark must attribute
every output to one known model, so a silent switch to another model would
corrupt its results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from rbcore.config import Settings
from rbcore.llm.base import LLMError, LLMRefusalError, LLMRequest, LLMResponse

if TYPE_CHECKING:
    from anthropic.types import MessageParam


class AnthropicClient:
    """:class:`rbcore.llm.LLMClient` backed by the Claude Messages API."""

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        sdk_client: Any | None = None,
        max_retries: int = 2,
    ) -> None:
        """Create the client without making any request.

        Args:
            model: Claude model ID, from configuration.
            api_key: API key; required unless ``sdk_client`` is given.
            sdk_client: A pre-built ``anthropic.Anthropic`` (or a stand-in
                with the same ``messages.create`` shape, for tests).
            max_retries: SDK retry count for 408/409/429/5xx and connection
                errors.

        Raises:
            LLMError: If the model ID is empty, no key or client is given,
                or the ``anthropic`` package is not installed.
        """
        if not model:
            raise LLMError("a model ID is required (set it in configuration, not in code)")
        self.model = model
        if sdk_client is not None:
            self._sdk = sdk_client
            return
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set; use FakeLLMClient instead")
        try:
            # Optional dependency, imported on demand so tests never need it.
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "the anthropic package is not installed; install researchbridge-rbcore[anthropic]"
            ) from exc
        self._sdk = anthropic.Anthropic(api_key=api_key, max_retries=max_retries)

    @classmethod
    def from_settings(cls, settings: Settings, role: str = "generation") -> AnthropicClient:
        """Build a client for a configured role.

        Args:
            settings: Runtime settings.
            role: "generation" or "judge".

        Returns:
            The client.

        Raises:
            rbcore.config.ConfigError: If the key or the role's model is unset.
        """
        return cls(settings.require_model(role), api_key=settings.require_anthropic_api_key())

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Send one request to the Messages API.

        Args:
            request: The request.

        Returns:
            The response, with the model ID the API reports.

        Raises:
            LLMRefusalError: If the model declines the request.
            LLMError: On API or connection errors (after SDK retries).
        """
        messages: list[MessageParam] = [
            {"role": m.role, "content": m.content} for m in request.messages
        ]
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }
        # Only send optional fields that were set: some models reject sampling params.
        if request.system is not None:
            kwargs["system"] = request.system
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        response = self._create(kwargs)
        if response.stop_reason == "refusal":
            raise LLMRefusalError(f"model {response.model} declined the request")
        text = "".join(block.text for block in response.content if block.type == "text")
        return LLMResponse(
            text=text,
            model=response.model,
            stop_reason=response.stop_reason,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            prompt_version=request.prompt_version,
        )

    def _create(self, kwargs: dict[str, Any]) -> Any:
        """Call ``messages.create``, translating SDK errors into :class:`LLMError`.

        Args:
            kwargs: Request parameters.

        Returns:
            The SDK's message object.

        Raises:
            LLMError: On any SDK error.
        """
        try:
            return self._sdk.messages.create(**kwargs)
        except Exception as exc:
            # The SDK's error classes all derive from anthropic.AnthropicError;
            # matching by module avoids importing the optional package here.
            if type(exc).__module__.startswith("anthropic"):
                raise LLMError(f"Claude API call failed: {type(exc).__name__}: {exc}") from exc
            raise
