"""Tests of the optional baseline adapters, using stand-in modules (no models, no downloads)."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

from rbbench.baselines import (
    AlignScoreScorer,
    BaselineUnavailableError,
    ForbiddenModelError,
    MiniCheckScorer,
    QAFactEvalScorer,
    availability,
)

PAIRS = [("Synthetic source.", "Synthetic claim one."), ("Synthetic source.", "Claim two.")]


def _module(name: str, **attributes: Any) -> types.ModuleType:
    """Build a stand-in module with the given attributes."""
    module = types.ModuleType(name)
    for key, value in attributes.items():
        setattr(module, key, value)
    return module


def test_missing_packages_raise_with_instructions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without the optional packages each adapter explains how to enable it."""
    for name in ("alignscore", "minicheck", "minicheck.minicheck", "qafacteval"):
        monkeypatch.setitem(sys.modules, name, None)
    with pytest.raises(BaselineUnavailableError, match=r"benchmark/README\.md"):
        AlignScoreScorer("ckpt")
    with pytest.raises(BaselineUnavailableError, match="not installed"):
        MiniCheckScorer()
    with pytest.raises(BaselineUnavailableError):
        QAFactEvalScorer("models")
    with pytest.raises(BaselineUnavailableError, match="ckpt_path"):
        AlignScoreScorer("")


def test_bespoke_minicheck_is_refused_before_any_import() -> None:
    """The CC BY-NC 7B checkpoint (and unknown ones) are never loaded."""
    with pytest.raises(ForbiddenModelError):
        MiniCheckScorer("Bespoke-MiniCheck-7B")
    with pytest.raises(ForbiddenModelError):
        MiniCheckScorer("some-other-model")


def test_alignscore_adapter_passes_contexts_and_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    """AlignScore receives sources as contexts and claims as claims."""
    calls: dict[str, Any] = {}

    class StandIn:
        """Records constructor and score arguments."""

        def __init__(self, **kwargs: Any) -> None:
            """Record the constructor arguments."""
            calls["init"] = kwargs

        def score(self, contexts: list[str], claims: list[str]) -> list[float]:
            """Return fixed scores."""
            calls["score"] = (contexts, claims)
            return [0.25, 0.75]

    monkeypatch.setitem(sys.modules, "alignscore", _module("alignscore", AlignScore=StandIn))
    scorer = AlignScoreScorer("/models/AlignScore-large.ckpt")
    assert scorer.score(PAIRS) == [0.25, 0.75]
    assert calls["init"]["ckpt_path"] == "/models/AlignScore-large.ckpt"
    assert calls["init"]["evaluation_mode"] == "nli_sp"
    assert calls["score"] == ([s for s, _ in PAIRS], [c for _, c in PAIRS])


def test_minicheck_adapter_returns_probabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    """MiniCheck's raw probabilities (second return value) are the scores."""

    class StandIn:
        """Mimics MiniCheck's score signature."""

        def __init__(self, model_name: str, cache_dir: str) -> None:
            """Record the model name."""
            self.model_name = model_name

        def score(self, docs: list[str], claims: list[str]) -> tuple[Any, ...]:
            """Return labels, probabilities and two unused values."""
            return [1, 0], [0.9, 0.1], None, None

    package = _module("minicheck")
    monkeypatch.setitem(sys.modules, "minicheck", package)
    monkeypatch.setitem(
        sys.modules, "minicheck.minicheck", _module("minicheck.minicheck", MiniCheck=StandIn)
    )
    assert MiniCheckScorer("flan-t5-large").score(PAIRS) == [0.9, 0.1]


def test_qafacteval_adapter_reads_lerc_quip(monkeypatch: pytest.MonkeyPatch) -> None:
    """QAFactEval gets one summary list per pair; the LERC-QuIP score is returned."""
    seen: dict[str, Any] = {}

    class StandIn:
        """Mimics QAFactEval's batch scoring."""

        def __init__(self, **kwargs: Any) -> None:
            """Record the model paths."""
            seen["init"] = kwargs

        def score_batch_qafacteval(
            self, sources: list[str], summaries: list[list[str]], return_qa_pairs: bool
        ) -> list[Any]:
            """Return one nested result per pair."""
            seen["summaries"] = summaries
            return [[{"qa-eval": {"lerc_quip": 0.5}}, []] for _ in sources]

    monkeypatch.setitem(sys.modules, "qafacteval", _module("qafacteval", QAFactEval=StandIn))
    assert QAFactEvalScorer("/m").score(PAIRS) == [0.5, 0.5]
    assert seen["summaries"] == [["Synthetic claim one."], ["Claim two."]]
    assert seen["init"]["lerc_quip_path"] == "/m/quip-512-mocha"


def test_availability_reports_without_importing() -> None:
    """In the default environment no baseline package is installed."""
    assert availability() == {"alignscore": False, "minicheck": False, "qafacteval": False}
