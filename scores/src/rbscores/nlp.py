"""Loading the spaCy pipeline used for tokenisation, tagging and parsing.

The default is spaCy's small English pipeline ``en_core_web_sm`` (MIT;
trained by Explosion on OntoNotes 5 under a commercial licence they hold, plus
WordNet 3.0). It is installed into the virtualenv by the lock file, never
committed. Another installed pipeline can be chosen with the
``RB_SCORES_SPACY_MODEL`` environment variable, but every score definition and
the packaged reference statistics were produced with the default, so changing
it changes the scores.

The named-entity recogniser is excluded when loading: no score uses it
(it mislabels rare technical words as people and places), and parsing is
faster without it.

scispaCy's biomedical pipelines were evaluated and not adopted: their weights
are CC BY-SA 3.0 and the current release requires spaCy < 3.8 (see
docs/licence-inventory.md).
"""

from __future__ import annotations

import functools
import os

import spacy
from spacy.language import Language

DEFAULT_MODEL = "en_core_web_sm"
MODEL_ENV_VAR = "RB_SCORES_SPACY_MODEL"


class ModelNotInstalledError(RuntimeError):
    """Raised when the configured spaCy pipeline is not installed."""


def configured_model_name() -> str:
    """Return the spaCy pipeline name to use.

    Returns:
        ``RB_SCORES_SPACY_MODEL`` when set and non-blank, else :data:`DEFAULT_MODEL`.
    """
    return os.environ.get(MODEL_ENV_VAR, "").strip() or DEFAULT_MODEL


@functools.cache
def load_pipeline(name: str | None = None) -> Language:
    """Load (once per process) a spaCy pipeline with a dependency parser.

    Args:
        name: Pipeline package name; defaults to :func:`configured_model_name`.

    Returns:
        The loaded pipeline.

    Raises:
        ModelNotInstalledError: If the package is not installed, or it has no
            parser (syntactic depth, passive voice and noun chunks need one).
    """
    model = name or configured_model_name()
    try:
        nlp = spacy.load(model, exclude=["ner"])
    except OSError as exc:
        raise ModelNotInstalledError(
            f"spaCy pipeline {model!r} is not installed; run `make setup` "
            f"(or unset {MODEL_ENV_VAR} to use {DEFAULT_MODEL})"
        ) from exc
    if "parser" not in nlp.pipe_names:
        raise ModelNotInstalledError(f"spaCy pipeline {model!r} has no dependency parser")
    return nlp


def pipeline_label(nlp: Language) -> str:
    """Name a loaded pipeline for provenance records.

    Args:
        nlp: A loaded spaCy pipeline.

    Returns:
        Package-style name and version, e.g. ``en_core_web_sm-3.8.0``.
    """
    meta = nlp.meta
    return f"{meta.get('lang', 'xx')}_{meta.get('name', 'unknown')}-{meta.get('version', '?')}"
