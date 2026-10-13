"""The selection config (``benchmark/selection/slots_v1.yaml``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from rbbench.selection.classify import StudyType

_DATE_RANGE = re.compile(r"^\d{4}:\d{4}$")


class SelectionConfigError(ValueError):
    """Raised when the selection config is invalid."""


@dataclass(frozen=True, slots=True)
class Journal:
    """A journal in the reference datasets.

    Attributes:
        key: Config key, e.g. "plos_ntd".
        query: PubMed journal clause, e.g. '"PLoS Negl Trop Dis"[ta]'.
        label: Display name.
    """

    key: str
    query: str
    label: str


@dataclass(frozen=True, slots=True)
class Slot:
    """One of the twelve slots to fill.

    Attributes:
        id: Slot ID, e.g. "S01".
        study_type: The study type the slot needs.
        journals: Journal keys the slot draws from.
        require_lay_summary: Whether candidates need an expert lay summary.
    """

    id: str
    study_type: StudyType
    journals: tuple[str, ...]
    require_lay_summary: bool


@dataclass(frozen=True, slots=True)
class SelectionConfig:
    """The parsed selection config.

    Attributes:
        version: Config version, e.g. "slots_v1".
        status: "PROPOSED" until the owner approves the shortlist.
        seed: Seed for the deterministic screening order.
        date_range: PubMed ``[dp]`` range, e.g. "2015:2022".
        candidates_per_slot: How many candidates to propose per slot.
        max_screen_per_slot: Upper bound on PMIDs screened per slot.
        min_body_words: Minimum body length.
        max_body_words: Maximum body length.
        journals: Journals by key.
        study_type_filters: PubMed filter per study type.
        slots: The slots, in order.
    """

    version: str
    status: str
    seed: str
    date_range: str
    candidates_per_slot: int
    max_screen_per_slot: int
    min_body_words: int
    max_body_words: int
    journals: dict[str, Journal]
    study_type_filters: dict[StudyType, str]
    slots: tuple[Slot, ...]

    def query_for(self, slot: Slot) -> str:
        """Build the PubMed query for a slot.

        Args:
            slot: The slot.

        Returns:
            Journals OR-ed, the study-type filter, the date range, and the PMC
            subset (only articles with a PMC copy can pass the licence check).
        """
        journals = " OR ".join(self.journals[key].query for key in slot.journals)
        study_filter = self.study_type_filters[slot.study_type]
        return f'({journals}) AND ({study_filter}) AND {self.date_range}[dp] AND "pubmed pmc"[sb]'


def load_selection_config(path: Path) -> SelectionConfig:
    """Load and validate a selection config.

    Args:
        path: The YAML file.

    Returns:
        The config.

    Raises:
        SelectionConfigError: If a field is missing or inconsistent.
    """
    raw: Any = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise SelectionConfigError(f"{path}: expected a mapping")
    try:
        journals = {
            key: Journal(key, str(value["query"]), str(value["label"]))
            for key, value in raw["journals"].items()
        }
        filters = {StudyType(key): str(value) for key, value in raw["study_types"].items()}
        default_lay = bool(raw.get("require_lay_summary", True))
        slots = tuple(
            Slot(
                id=str(item["id"]),
                study_type=StudyType(item["study_type"]),
                journals=tuple(str(j) for j in item["journals"]),
                require_lay_summary=bool(item.get("require_lay_summary", default_lay)),
            )
            for item in raw["slots"]
        )
        config = SelectionConfig(
            version=str(raw["version"]),
            status=str(raw["status"]),
            seed=str(raw["seed"]),
            date_range=str(raw["date_range"]),
            candidates_per_slot=int(raw["candidates_per_slot"]),
            max_screen_per_slot=int(raw["max_screen_per_slot"]),
            min_body_words=int(raw["min_body_words"]),
            max_body_words=int(raw["max_body_words"]),
            journals=journals,
            study_type_filters=filters,
            slots=slots,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise SelectionConfigError(f"{path}: {exc}") from exc

    # Cross-field checks that the parser alone cannot express.
    if not _DATE_RANGE.match(config.date_range):
        raise SelectionConfigError(f"{path}: date_range must look like 2015:2022")
    ids = [slot.id for slot in config.slots]
    if len(ids) != len(set(ids)):
        raise SelectionConfigError(f"{path}: duplicate slot IDs")
    for slot in config.slots:
        unknown = [key for key in slot.journals if key not in journals]
        if unknown or not slot.journals:
            raise SelectionConfigError(f"{path}: slot {slot.id} has unknown journals {unknown}")
        if slot.study_type not in filters:
            raise SelectionConfigError(f"{path}: no filter for {slot.study_type.value}")
    if config.candidates_per_slot < 1 or config.max_screen_per_slot < config.candidates_per_slot:
        raise SelectionConfigError(f"{path}: invalid candidates_per_slot / max_screen_per_slot")
    return config
