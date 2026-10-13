"""Optional automatic faithfulness baselines behind one interface.

Plan.md Phase 1 compares the LLM judge with automatic metrics. The three
adapters wrap the published packages; none is a dependency of rbbench, and
nothing here downloads a model. Each adapter imports its package only when
constructed and raises :class:`BaselineUnavailableError` with installation
instructions when it is missing.

* AlignScore: code MIT (yuh-zha/AlignScore), weights MIT (HF yzha/AlignScore);
  needs a local checkpoint path.
* MiniCheck: code Apache-2.0 (Liyan06/MiniCheck); the roberta-large,
  deberta-v3-large and flan-t5-large checkpoints are MIT. Bespoke-MiniCheck-7B
  is CC BY-NC 4.0 and is refused.
* QAFactEval: code BSD-3-Clause (salesforce/QAFactEval); the models from its
  download script have a licence to verify before use. Heavy (AllenNLP).

How to enable one is documented in benchmark/README.md. The scores are
claim-level "is this supported by the source" probabilities, so they can be
compared with the judge's ``support`` code on the same claims.
"""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Sequence
from types import ModuleType
from typing import Any, Protocol

# MiniCheck checkpoints whose weights are MIT-licensed (checked on Hugging Face
# 2026-10-13). Bespoke-MiniCheck-7B is CC BY-NC 4.0 and is never allowed.
MINICHECK_ALLOWED = ("roberta-large", "deberta-v3-large", "flan-t5-large")
FORBIDDEN_MODELS = ("Bespoke-MiniCheck-7B",)


class BaselineUnavailableError(RuntimeError):
    """Raised when a baseline's package is not installed or its settings are missing."""


class ForbiddenModelError(ValueError):
    """Raised when a baseline is asked to use weights with a forbidden licence."""


class FactualityScorer(Protocol):
    """Anything that scores (source, claim) pairs in [0, 1]."""

    name: str

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Score each claim against its source.

        Args:
            pairs: ``(source_text, claim)`` pairs.

        Returns:
            One score per pair; higher means better supported.
        """
        ...


def _require(module: str, install_hint: str) -> ModuleType:
    """Import an optional module or explain how to install it.

    Args:
        module: Dotted module name.
        install_hint: What to run to install it.

    Returns:
        The module.

    Raises:
        BaselineUnavailableError: If the module cannot be imported.
    """
    try:
        return importlib.import_module(module)
    except ImportError as exc:
        raise BaselineUnavailableError(
            f"the optional baseline package {module!r} is not installed; {install_hint}"
        ) from exc


class AlignScoreScorer:
    """AlignScore (Zha et al., ACL 2023)."""

    name = "alignscore"

    def __init__(
        self,
        ckpt_path: str,
        *,
        model: str = "roberta-large",
        device: str = "cpu",
        batch_size: int = 16,
        evaluation_mode: str = "nli_sp",
    ) -> None:
        """Load the scorer.

        Args:
            ckpt_path: Local path to an AlignScore checkpoint (download it
                yourself from huggingface.co/yzha/AlignScore; MIT).
            model: Backbone, "roberta-base" or "roberta-large", matching the checkpoint.
            device: Torch device, e.g. "cpu" or "cuda:0".
            batch_size: Inference batch size.
            evaluation_mode: AlignScore mode; "nli_sp" is the paper's default.

        Raises:
            BaselineUnavailableError: If alignscore is not installed or no
                checkpoint path is given.
        """
        # Nothing is ever downloaded here: the checkpoint must already be on disk.
        if not ckpt_path:
            raise BaselineUnavailableError("AlignScore needs ckpt_path (a downloaded checkpoint)")
        # Import lazily so the optional package is needed only when this baseline is used.
        module = _require("alignscore", "see benchmark/README.md, 'Automatic baselines'")
        self._scorer: Any = module.AlignScore(
            model=model,
            batch_size=batch_size,
            device=device,
            ckpt_path=ckpt_path,
            evaluation_mode=evaluation_mode,
        )

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Score pairs with AlignScore.

        Args:
            pairs: ``(source_text, claim)`` pairs.

        Returns:
            AlignScore values.
        """
        scores = self._scorer.score(contexts=[s for s, _ in pairs], claims=[c for _, c in pairs])
        return [float(s) for s in scores]


class MiniCheckScorer:
    """MiniCheck (Tang et al., EMNLP 2024), MIT-licensed checkpoints only."""

    name = "minicheck"

    def __init__(
        self, model_name: str = "flan-t5-large", *, cache_dir: str = "data/models"
    ) -> None:
        """Load the scorer.

        Args:
            model_name: One of :data:`MINICHECK_ALLOWED`.
            cache_dir: Where MiniCheck caches the checkpoint (keep it in the
                gitignored data directory).

        Raises:
            ForbiddenModelError: For Bespoke-MiniCheck-7B (CC BY-NC) or any
                checkpoint not known to be MIT-licensed.
            BaselineUnavailableError: If minicheck is not installed.
        """
        if model_name in FORBIDDEN_MODELS or model_name not in MINICHECK_ALLOWED:
            raise ForbiddenModelError(
                f"MiniCheck model {model_name!r} is not allowed; use one of {MINICHECK_ALLOWED}"
            )
        module = _require("minicheck.minicheck", "see benchmark/README.md, 'Automatic baselines'")
        self._scorer: Any = module.MiniCheck(model_name=model_name, cache_dir=cache_dir)

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Score pairs with MiniCheck's support probability.

        Args:
            pairs: ``(source_text, claim)`` pairs.

        Returns:
            Probabilities that each claim is supported.
        """
        _labels, probabilities, _, _ = self._scorer.score(
            docs=[s for s, _ in pairs], claims=[c for _, c in pairs]
        )
        return [float(p) for p in probabilities]


class QAFactEvalScorer:
    """QAFactEval (Fabbri et al., NAACL 2022)."""

    name = "qafacteval"

    def __init__(self, model_folder: str, *, cuda_device: int = -1) -> None:
        """Load the scorer.

        Args:
            model_folder: Folder with the models from QAFactEval's
                ``download_models.sh`` (check their licences first).
            cuda_device: CUDA device index, or -1 for CPU.

        Raises:
            BaselineUnavailableError: If qafacteval is not installed or no
                model folder is given.
        """
        if not model_folder:
            raise BaselineUnavailableError("QAFactEval needs model_folder (downloaded models)")
        module = _require("qafacteval", "see benchmark/README.md, 'Automatic baselines'")
        self._metric: Any = module.QAFactEval(
            lerc_quip_path=f"{model_folder}/quip-512-mocha",
            generation_model_path=f"{model_folder}/generation/model.tar.gz",
            answering_model_dir=f"{model_folder}/answering",
            lerc_model_path=f"{model_folder}/lerc/model.tar.gz",
            lerc_pretrained_model_path=f"{model_folder}/lerc/pretraining.tar.gz",
            cuda_device=cuda_device,
            use_lerc_quip=True,
            verbose=False,
            generation_batch_size=32,
            answering_batch_size=32,
            lerc_batch_size=8,
        )

    def score(self, pairs: Sequence[tuple[str, str]]) -> list[float]:
        """Score pairs with QAFactEval's LERC-QuIP score.

        Args:
            pairs: ``(source_text, claim)`` pairs.

        Returns:
            One score per pair.
        """
        results = self._metric.score_batch_qafacteval(
            [s for s, _ in pairs], [[c] for _, c in pairs], return_qa_pairs=True
        )
        return [float(result[0]["qa-eval"]["lerc_quip"]) for result in results]


SCORERS: dict[str, type[AlignScoreScorer] | type[MiniCheckScorer] | type[QAFactEvalScorer]] = {
    AlignScoreScorer.name: AlignScoreScorer,
    MiniCheckScorer.name: MiniCheckScorer,
    QAFactEvalScorer.name: QAFactEvalScorer,
}


def availability() -> dict[str, bool]:
    """Report which baseline packages are importable, without loading any model.

    Returns:
        Baseline name -> whether its package can be imported.
    """
    modules = {"alignscore": "alignscore", "minicheck": "minicheck", "qafacteval": "qafacteval"}
    return {name: importlib.util.find_spec(module) is not None for name, module in modules.items()}
