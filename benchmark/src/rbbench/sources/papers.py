"""Where ingest gets papers from: shortlist candidates or the committed fixtures."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from rbbench.ingest import EvidenceRecord, PaperSource
from rbbench.selection.shortlist import Candidate
from rbbench.sources import pmc
from rbcore.http import PoliteFetcher
from rbcore.licences import LicenceField

# Fixtures used by the dry run: CC BY 4.0 files committed in Phase 0, with
# attribution in their README. The Europe PMC copy is included on purpose: it
# carries only licence prose, so the gate must refuse it.
DRY_RUN_FIXTURES = (
    "elife-65180-pmc-s3.xml",
    "elife-61907-pmc-s3.xml",
    "elife-93719-pmc-s3.xml",
    "elife-93719-europepmc.xml",
)


def candidate_sources(candidates: Sequence[Candidate], fetcher: PoliteFetcher) -> list[PaperSource]:
    """Fetch each candidate's metadata and JATS from the PMC Cloud Service.

    The licence evidence is re-read from the metadata JSON (from the cache when
    the shortlist was built in the same data directory), so ingest gates on
    the primary source rather than on the CSV.

    Args:
        candidates: Shortlist candidates.
        fetcher: The polite fetcher.

    Returns:
        One source per candidate, in order.

    Raises:
        rbbench.sources.pmc.PmcError: If metadata or JATS is unusable.
        rbcore.http.FetchError: If a download fails.
    """
    sources: list[PaperSource] = []
    for candidate in candidates:
        record = pmc.fetch_record(fetcher, candidate.pmcid, candidate.pmc_version)
        evidence = (
            EvidenceRecord(
                field=LicenceField.PMC_LICENSE_CODE.value,
                value=record.license_code or "",
                url=record.json_url,
                retrieved=pmc.retrieved_on(fetcher, record.json_url).isoformat(),
            ),
        )
        sources.append(
            PaperSource(
                paper_key=record.key,
                jats=pmc.fetch_jats(fetcher, record),
                evidence=evidence if record.license_code else (),
                metadata={
                    "slot": candidate.slot,
                    "option": candidate.option,
                    "study_type": candidate.study_type,
                    "pmid": candidate.pmid,
                    "pmcid": candidate.pmcid,
                    "is_retracted": record.is_retracted,
                },
            )
        )
    return sources


def fixture_sources(
    fixtures_dir: Path, names: Sequence[str] = DRY_RUN_FIXTURES
) -> list[PaperSource]:
    """Load committed JATS fixtures with the licence evidence their manifest records.

    The evidence URL points at the manifest, not at PMC, because that is where
    the value was recorded (Phase 0, retrieved on the manifest's date). The
    Europe PMC copy gets no PMC evidence: it is a different source document.

    Args:
        fixtures_dir: Directory with the fixtures and ``manifest.json``.
        names: Fixture file names, in order.

    Returns:
        One source per fixture; the paper key is the file stem.

    Raises:
        KeyError: If a name is not in the manifest.
    """
    manifest_path = fixtures_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {entry["file"]: entry for entry in manifest["fixtures"]}
    sources: list[PaperSource] = []
    for name in names:
        entry = entries[name]
        from_pmc = "pmc-oa-opendata" in entry["source_url"]
        evidence = (
            (
                EvidenceRecord(
                    field=LicenceField.PMC_LICENSE_CODE.value,
                    value=entry["pmc_license_code"],
                    url=f"{manifest_path.name} (recorded from {entry['source_url']})",
                    retrieved=manifest["retrieved"],
                ),
            )
            if from_pmc
            else ()
        )
        sources.append(
            PaperSource(
                paper_key=Path(name).stem,
                jats=(fixtures_dir / name).read_bytes(),
                evidence=evidence,
                metadata={"fixture": name, "source_url": entry["source_url"], "doi": entry["doi"]},
            )
        )
    return sources
