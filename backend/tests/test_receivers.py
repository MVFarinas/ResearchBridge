"""Ingestion's reactions to licence review resolutions (synthetic data, in-memory queue)."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import date
from typing import Any

import pytest
from procrastinate import App
from procrastinate.testing import InMemoryConnector
from support import jobs, synthetic_code, synthetic_content, synthetic_version

from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import (
    ContentState,
    GateStatus,
    LicenceRecord,
    LicenceReview,
    PaperVersion,
    ReviewStatus,
)
from rb_backend.corpus.reviews import resolve_review
from rb_backend.ingestion import receivers
from rb_backend.ingestion.pmc import BASE_URL, PmcBucket
from rbcore.http import PoliteFetcher

pytestmark = pytest.mark.django_db

TODAY = date(2026, 10, 13)
SYNTHETIC_XML_URL = f"{BASE_URL}/PMC900000001.1/PMC900000001.1.xml?md5=0"

type CaptureOnCommit = Callable[..., AbstractContextManager[list[Callable[[], Any]]]]


@pytest.fixture
def use_bucket(bucket: PmcBucket, monkeypatch: pytest.MonkeyPatch) -> PmcBucket:
    """Make the receivers use the test bucket (and its temporary cache)."""
    monkeypatch.setattr(receivers, "get_bucket", lambda: bucket)
    return bucket


def removed_version_under_review() -> tuple[PaperVersion, LicenceRecord]:
    """A synthetic version whose text a reviewer's rejection removed, back under review.

    Returns:
        The version (content removed, gate status review) and its licence code.
    """
    # A code nobody recognises goes to review; the reviewer rejects it.
    version = synthetic_version()
    synthetic_content(version)
    code = synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version, today=TODAY)
    resolve_review(
        LicenceReview.objects.get(),
        approve=False,
        licence_value="",
        note="No licence found (synthetic).",
        reviewer=None,
    )

    # New, still unrecognised, evidence opens a fresh review of the removed version.
    code.raw_value = "ANOTHER-UNKNOWN"
    code.save()
    assert evaluate_version(version, today=TODAY) == GateStatus.REVIEW
    version.refresh_from_db()
    assert version.content_state == ContentState.REMOVED
    return version, code


def test_approving_a_removed_version_queues_its_text_after_commit(
    queue: tuple[App, InMemoryConnector],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """Approval of a version whose text was removed sends it to the worker at once."""
    # Arrange: a removed version with an open review.
    _, connector = queue
    removed_version_under_review()
    review = LicenceReview.objects.get(status=ReviewStatus.OPEN)

    # Act: approve it; the job is queued only when the transaction commits.
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        status = resolve_review(
            review, approve=True, licence_value="CC BY", note="Checked.", reviewer=None
        )
        assert jobs(connector) == []
    assert len(callbacks) == 1

    # Still pending (no text yet), and the worker has the article to fetch.
    assert status == GateStatus.PENDING
    assert [job["args"] for job in jobs(connector)] == [{"pmcid": "PMC900000001"}]


def test_approving_a_version_with_its_text_queues_nothing(
    queue: tuple[App, InMemoryConnector],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """A version that still has its text needs no fetch after approval."""
    _, connector = queue
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version, today=TODAY)
    with django_capture_on_commit_callbacks(execute=True):
        status = resolve_review(
            LicenceReview.objects.get(),
            approve=True,
            licence_value="CC BY",
            note="Checked.",
            reviewer=None,
        )
    assert status == GateStatus.APPROVED
    assert jobs(connector) == []


def test_rejection_deletes_the_cached_xml_after_commit(
    use_bucket: PmcBucket,
    fetcher: PoliteFetcher,
    queue: tuple[App, InMemoryConnector],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """A reviewer's rejection removes the XML from the download cache, not just the database."""
    # Arrange: a version under review whose XML sits in the download cache.
    _, connector = queue
    version = synthetic_version()
    version.content_url = SYNTHETIC_XML_URL
    version.save()
    synthetic_content(version)
    synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version, today=TODAY)
    cached = fetcher.cache_path(SYNTHETIC_XML_URL)
    assert cached is not None
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(b"<synthetic-cached-xml/>")

    # Act: reject. The file goes only once the rejection commits.
    with django_capture_on_commit_callbacks(execute=True):
        status = resolve_review(
            LicenceReview.objects.get(),
            approve=False,
            licence_value="",
            note="No licence (synthetic).",
            reviewer=None,
        )
        assert cached.exists()

    # Rejected, the cached copy is gone, and nothing is queued.
    assert status == GateStatus.REJECTED
    assert not cached.exists()
    assert jobs(connector) == []
