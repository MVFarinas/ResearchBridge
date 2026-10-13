"""LLM client interface, a deterministic fake, and the real Claude client.

Code that needs an LLM takes an :class:`LLMClient` argument. Tests and dry
runs pass :class:`FakeLLMClient`; production builds an
:class:`AnthropicClient` from :class:`rbcore.config.Settings`. Importing this
package never imports the ``anthropic`` SDK.
"""

from rbcore.llm.anthropic_client import AnthropicClient
from rbcore.llm.base import (
    LLMClient,
    LLMError,
    LLMRefusalError,
    LLMRequest,
    LLMResponse,
    Message,
)
from rbcore.llm.fake import FAKE_MODEL, FakeLLMClient, request_fingerprint

__all__ = [
    "FAKE_MODEL",
    "AnthropicClient",
    "FakeLLMClient",
    "LLMClient",
    "LLMError",
    "LLMRefusalError",
    "LLMRequest",
    "LLMResponse",
    "Message",
    "request_fingerprint",
]
