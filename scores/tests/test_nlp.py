"""Tests for choosing and loading the spaCy pipeline."""

from __future__ import annotations

import pytest
import spacy
from spacy.language import Language

from rbscores import nlp as nlp_module
from rbscores.nlp import (
    DEFAULT_MODEL,
    MODEL_ENV_VAR,
    ModelNotInstalledError,
    configured_model_name,
    load_pipeline,
    pipeline_label,
)


def test_default_model_without_the_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the variable unset or blank, the default pipeline is used."""
    monkeypatch.delenv(MODEL_ENV_VAR, raising=False)
    assert configured_model_name() == DEFAULT_MODEL
    monkeypatch.setenv(MODEL_ENV_VAR, "   ")
    assert configured_model_name() == DEFAULT_MODEL


def test_environment_variable_names_the_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """The variable's value, stripped, chooses the pipeline."""
    monkeypatch.setenv(MODEL_ENV_VAR, " en_core_web_md ")
    assert configured_model_name() == "en_core_web_md"


def test_missing_pipeline_raises_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """An uninstalled package's OSError from spaCy becomes ModelNotInstalledError."""

    def not_installed(name: str, **_: object) -> Language:
        """Fail as spaCy does for a package that is not installed."""
        raise OSError(f"[E050] Can't find model '{name}'")

    monkeypatch.setattr(nlp_module.spacy, "load", not_installed)
    with pytest.raises(ModelNotInstalledError, match="'rb-test-missing' is not installed"):
        load_pipeline("rb-test-missing")


def test_pipeline_without_parser_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pipeline with no dependency parser cannot compute the features."""
    monkeypatch.setattr(nlp_module.spacy, "load", lambda name, **_: spacy.blank("en"))
    with pytest.raises(ModelNotInstalledError, match="has no dependency parser"):
        load_pipeline("rb-test-no-parser")


def test_default_pipeline_loads_once_and_is_labelled(nlp: Language) -> None:
    """The installed default has a parser, no NER, and a provenance label."""
    assert load_pipeline() is nlp
    assert "parser" in nlp.pipe_names
    assert "ner" not in nlp.pipe_names
    assert pipeline_label(nlp).startswith("en_core_web_sm-")
