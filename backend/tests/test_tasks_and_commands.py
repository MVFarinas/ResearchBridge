"""Worker tasks and management commands (in-memory queue, recorded bucket)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone
from procrastinate import App
from procrastinate.contrib.django import app as procrastinate_app
from procrastinate.testing import InMemoryConnector
from support import synthetic_code, synthetic_content, synthetic_version

from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import GateStatus, Paper, PaperVersion
from rb_backend.ingestion import tasks
from rb_backend.ingestion.management.commands import ingest_pmc, recheck_licences
from rb_backend.ingestion.pmc import PmcBucket


@pytest.fixture
def queue() -> Iterator[tuple[App, InMemoryConnector]]:
    """The Procrastinate app with an in-memory connector instead of Postgres."""
    connector = InMemoryConnector()
    with procrastinate_app.replace_connector(connector) as app:
        yield app, connector


@pytest.fixture
def use_bucket(bucket: PmcBucket, monkeypatch: pytest.MonkeyPatch) -> PmcBucket:
    """Make tasks and commands use the recorded bucket instead of the real one."""
    for module in (tasks, ingest_pmc, recheck_licences):
        monkeypatch.setattr(module, "get_bucket", lambda: bucket)
    return bucket


def jobs(connector: InMemoryConnector) -> list[dict[str, Any]]:
    """The queued jobs as dictionaries."""
    return [dict(job) for job in connector.jobs.values()]


def run(command: str, *args: str) -> str:
    """Run a management command and return its standard output."""
    out = StringIO()
    call_command(command, *args, stdout=out, stderr=StringIO())
    return out.getvalue()


def checked(version: PaperVersion, days_ago: int) -> PaperVersion:
    """Mark a synthetic version as last checked some days ago."""
    version.last_checked_at = timezone.now() - timedelta(days=days_ago)
    version.save()
    return version


# --- Tasks --------------------------------------------------------------------------


def test_defer_ingest_queues_once_per_article(queue: tuple[App, InMemoryConnector]) -> None:
    """The PMC ID is the queueing lock, so an article is never queued twice."""
    _, connector = queue
    assert tasks.defer_ingest("PMC10718527") is True
    assert tasks.defer_ingest("PMC10718527") is False
    (job,) = jobs(connector)
    assert (job["task_name"], job["queue_name"], job["args"]) == (
        "rb.ingest_pmc_article",
        "ingestion",
        {"pmcid": "PMC10718527"},
    )
    assert tasks.defer_many(["PMC1", "PMC1", "PMC2"]) == (2, 1)


@pytest.mark.django_db(transaction=True)
def test_worker_runs_ingestion_jobs(
    queue: tuple[App, InMemoryConnector], use_bucket: PmcBucket
) -> None:
    """A real (in-memory) worker run executes the queued ingestion."""
    app, connector = queue
    tasks.defer_many(["PMC10718527", "PMC13641010"])
    app.run_worker(queues=["ingestion"], wait=False, install_signal_handlers=False)
    assert {job["status"] for job in jobs(connector)} == {"succeeded"}
    statuses = dict(PaperVersion.objects.values_list("source_version_id", "gate_status"))
    assert statuses == {
        "PMC10718527.1": GateStatus.APPROVED,
        "PMC13641010.1": GateStatus.REJECTED,
    }


@pytest.mark.django_db
def test_stale_pmcids_are_oldest_first() -> None:
    """Only current versions not checked within the window are returned, never-checked first."""
    # Arrange: stale, fresh, non-current and never-checked (created last) versions.
    checked(synthetic_version(pmcid="PMC900000001"), days_ago=10)
    checked(synthetic_version(pmcid="PMC900000002"), days_ago=30)
    checked(synthetic_version(pmcid="PMC900000003"), days_ago=1)
    checked(synthetic_version(pmcid="PMC900000004", is_current=False), days_ago=99)
    never = synthetic_version(pmcid="PMC900000005")
    assert never.last_checked_at is None

    # A never-checked version is the most overdue, so it comes first and survives a limit of 1.
    assert tasks.stale_pmcids(max_age=timedelta(days=7), limit=10) == [
        "PMC900000005",
        "PMC900000002",
        "PMC900000001",
    ]
    assert tasks.stale_pmcids(max_age=timedelta(days=7), limit=1) == ["PMC900000005"]


@pytest.mark.django_db
def test_periodic_recheck_queues_stale_articles(
    queue: tuple[App, InMemoryConnector], settings: Any
) -> None:
    """The daily task queues re-checks for stale articles, within the batch size."""
    _, connector = queue
    settings.RB_RECHECK_MAX_AGE_DAYS = 7
    settings.RB_RECHECK_BATCH_SIZE = 1
    checked(synthetic_version(pmcid="PMC900000001"), days_ago=10)
    checked(synthetic_version(pmcid="PMC900000002"), days_ago=20)
    tasks.recheck_stale_pmc_task(timestamp=0)
    assert [job["args"] for job in jobs(connector)] == [{"pmcid": "PMC900000002"}]


def test_periodic_task_is_registered() -> None:
    """The re-check is scheduled daily on the worker."""
    periodic = [
        p
        for p in procrastinate_app.periodic_registry.periodic_tasks.values()
        if p.task.name == "rb.recheck_stale_pmc"
    ]
    assert [p.cron for p in periodic] == ["23 4 * * *"]


# --- ingest_pmc ----------------------------------------------------------------------


@pytest.mark.django_db
def test_ingest_pmc_sync_ingests_and_summarises(use_bucket: PmcBucket) -> None:
    """--sync ingests inline and prints outcomes and gate statuses."""
    out = run("ingest_pmc", "--pmcid", "PMC10718527", "13641010", "--sync")
    assert "PMC10718527: created, gate approved, licence cc-by" in out
    assert "PMC13641010: created, gate rejected, licence tdm" in out
    assert "gate: {'approved': 1, 'rejected': 1}" in out


@pytest.mark.django_db
def test_ingest_pmc_searches_and_queues(
    queue: tuple[App, InMemoryConnector], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without --sync, discovered IDs become worker jobs; the search gets the filters."""
    _, connector = queue
    calls: list[tuple[str, int]] = []

    def fake_search(_fetcher: object, term: str, *, limit: int, api_key: str | None) -> list[str]:
        """Return synthetic IDs and record the search."""
        calls.append((term, limit))
        return ["PMC900000001", "PMC900000002"]

    monkeypatch.setattr(ingest_pmc, "search_pmc", fake_search)
    out = run(
        "ingest_pmc", "--limit", "3", "--query", "asthma", "--licence", "cc-by", "--pmcid", "PMC1"
    )
    expected_term = (
        "(asthma) AND (open_access[Filter] OR author_manuscript[Filter]) AND cc_by_license[Filter]"
    )
    assert calls == [(expected_term, 2)]
    assert "queued 3 job(s)" in out
    assert sorted(job["args"]["pmcid"] for job in jobs(connector)) == [
        "PMC1",
        "PMC900000001",
        "PMC900000002",
    ]


@pytest.mark.django_db
def test_ingest_pmc_skip_existing(queue: tuple[App, InMemoryConnector]) -> None:
    """--skip-existing leaves already stored articles alone."""
    _, connector = queue
    Paper.objects.create(pmcid="PMC900000001")
    out = run("ingest_pmc", "--pmcid", "PMC900000001", "PMC900000002", "--skip-existing")
    assert "1 article(s) to ingest" in out
    assert [job["args"]["pmcid"] for job in jobs(connector)] == ["PMC900000002"]


@pytest.mark.parametrize("args", [[], ["--limit", "0"], ["--pmcid", "not-an-id"]])
def test_ingest_pmc_rejects_bad_options(args: list[str]) -> None:
    """Missing or malformed options are command errors."""
    with pytest.raises(CommandError):
        call_command("ingest_pmc", *args, stdout=StringIO())


# --- recheck_licences and corpus_stats -------------------------------------------------


@pytest.mark.django_db
def test_recheck_offline_recomputes_from_stored_records() -> None:
    """--offline recomputes decisions without the network and reports changes."""
    version = synthetic_version()
    synthetic_content(version)
    code = synthetic_code(version, "CC BY")
    evaluate_version(version)
    code.raw_value = "TDM"
    code.save()

    out = run("recheck_licences", "--offline")
    assert f"{version.source_version_id}: approved -> rejected" in out
    assert "recomputed: {'rejected': 1}; 1 changed" in out


@pytest.mark.django_db
def test_recheck_sync_re_ingests(use_bucket: PmcBucket) -> None:
    """--sync re-checks articles at the source; an unchanged one reports unchanged."""
    run("ingest_pmc", "--pmcid", "PMC10718527", "--sync")
    out = run("recheck_licences", "--pmcid", "PMC10718527", "--sync")
    assert "re-checked: {'unchanged': 1}" in out


@pytest.mark.django_db
def test_recheck_default_queues_stale_articles(queue: tuple[App, InMemoryConnector]) -> None:
    """By default, re-checks of the matching articles go to the worker."""
    _, connector = queue
    checked(synthetic_version(pmcid="PMC900000001"), days_ago=10)
    checked(synthetic_version(pmcid="PMC900000002"), days_ago=1)
    out = run("recheck_licences", "--older-than-days", "7")
    assert "queued 1 re-check(s)" in out
    assert [job["args"]["pmcid"] for job in jobs(connector)] == ["PMC900000001"]


@pytest.mark.django_db
def test_corpus_stats_counts_by_licence_and_status(use_bucket: PmcBucket) -> None:
    """The statistics count licences, gate statuses, reviews and gated reads."""
    run("ingest_pmc", "--pmcid", "PMC10718527", "PMC7781593", "PMC13641010", "--sync")
    stats = json.loads(run("corpus_stats", "--json"))
    assert stats["totals"]["papers"] == 3
    assert stats["approved_by_licence"] == {"cc-by": 2}
    assert stats["rejected_by_licence"] == {"tdm": 1}
    assert stats["open_reviews_by_scope"] == {"figure": 1}
    assert stats["gated_querysets"]["displayable_papers"] == 2
    assert stats["figures_by_gate_status"]["review"] == 1
