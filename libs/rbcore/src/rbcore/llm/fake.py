"""A deterministic fake LLM client for tests and dry runs.

Its output is obviously synthetic: unless a test supplies its own responder,
every reply is a fixed marker plus a hash of the request. Responses carry
``synthetic=True`` so nothing downstream can mistake them for model output.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict

from rbcore.llm.base import LLMRequest, LLMResponse

FAKE_MODEL = "fake-deterministic"


def request_fingerprint(request: LLMRequest) -> str:
    """Return a stable SHA-256 hex digest of a request's content.

    Args:
        request: The request.

    Returns:
        64 hex characters; identical requests always give the same value.
    """
    payload = json.dumps(asdict(request), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _default_responder(request: LLMRequest) -> str:
    """Produce the default synthetic reply for a request.

    Args:
        request: The request.

    Returns:
        A marker string that names itself as synthetic.
    """
    return f"[SYNTHETIC FAKE LLM OUTPUT {request_fingerprint(request)[:16]}]"


class FakeLLMClient:
    """Deterministic :class:`rbcore.llm.LLMClient` that never touches a network.

    Attributes:
        calls: Every request received, in order, for assertions in tests.
    """

    def __init__(self, responder: Callable[[LLMRequest], str] | None = None) -> None:
        """Create the fake.

        Args:
            responder: Function mapping a request to reply text. Defaults to a
                synthetic marker derived from the request hash.
        """
        self._responder = responder or _default_responder
        self.calls: list[LLMRequest] = []

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Record the request and return a deterministic synthetic reply.

        Args:
            request: The request.

        Returns:
            A response with ``synthetic=True`` and whitespace-based token counts.
        """
        self.calls.append(request)
        text = self._responder(request)
        prompt_words = sum(len(m.content.split()) for m in request.messages)
        return LLMResponse(
            text=text,
            model=FAKE_MODEL,
            stop_reason="end_turn",
            input_tokens=prompt_words + len((request.system or "").split()),
            output_tokens=len(text.split()),
            prompt_version=request.prompt_version,
            synthetic=True,
        )
