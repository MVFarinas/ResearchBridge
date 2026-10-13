"""Django admin: read-mostly pages and the licence review form (synthetic data)."""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.urls import reverse
from support import synthetic_code, synthetic_content, synthetic_version

from rb_backend.corpus.gate import evaluate_version
from rb_backend.corpus.models import GateStatus, LicenceReview, PaperVersion, ReviewStatus

pytestmark = pytest.mark.django_db

MODELS = [
    "corpus/paper",
    "corpus/paperversion",
    "corpus/licencerecord",
    "corpus/permissionsblockrecord",
    "corpus/figure",
    "corpus/paragraph",
    "corpus/licencereview",
    "annotations/annotation",
    "annotations/vote",
    "annotations/report",
]


@pytest.fixture
def staff(client: Client) -> Client:
    """A client logged in as a (synthetic) superuser."""
    user = get_user_model().objects.create_superuser(
        "synthetic-admin",
        password="synthetic",  # noqa: S106 - test-only account
    )
    client.force_login(user)
    return client


@pytest.fixture
def review() -> LicenceReview:
    """An open review for a synthetic paper with conflicting sources."""
    version = synthetic_version()
    synthetic_content(version)
    synthetic_code(version, "SOMETHING-UNKNOWN")
    evaluate_version(version)
    return LicenceReview.objects.get()


@pytest.mark.parametrize("model", MODELS)
def test_changelists_render(staff: Client, review: LicenceReview, model: str) -> None:
    """Every registered model has a working list page."""
    response = staff.get(f"/admin/{model}/")
    assert response.status_code == 200


@pytest.mark.parametrize(
    "model", ["corpus/paper", "corpus/licencerecord", "annotations/annotation"]
)
def test_provenance_cannot_be_added_by_hand(staff: Client, model: str) -> None:
    """Papers, licence records and annotations are never created in the admin."""
    assert staff.get(f"/admin/{model}/add/").status_code == 403


def test_version_page_is_view_only(staff: Client, review: LicenceReview) -> None:
    """A version's page displays its decision but offers no save."""
    url = reverse("admin:corpus_paperversion_change", args=[review.version_id])
    response = staff.get(url)
    assert response.status_code == 200
    assert b'name="_save"' not in response.content
    assert staff.post(url, {}).status_code == 403


def test_review_form_approves_with_a_licence(staff: Client, review: LicenceReview) -> None:
    """Approving through the admin records the decision and re-runs the gate."""
    url = reverse("admin:corpus_licencereview_change", args=[review.pk])
    response = staff.post(
        url,
        {
            "decision": "approve",
            "licence": "https://creativecommons.org/licenses/by/4.0/",
            "note": "Publisher page says CC BY.",
        },
    )
    assert response.status_code == 302
    review.refresh_from_db()
    assert (review.status, review.resolved_family, review.reviewer_note) == (
        ReviewStatus.APPROVED,
        "cc-by",
        "Publisher page says CC BY.",
    )
    assert review.reviewer is not None
    assert PaperVersion.objects.get().gate_status == GateStatus.APPROVED


def test_review_form_refuses_unrecognised_licence(staff: Client, review: LicenceReview) -> None:
    """An approval without a recognised licence is a form error; nothing changes."""
    url = reverse("admin:corpus_licencereview_change", args=[review.pk])
    response = staff.post(url, {"decision": "approve", "licence": "free to use", "note": "x"})
    assert response.status_code == 200
    assert b"recognised licence" in response.content
    review.refresh_from_db()
    assert review.status == ReviewStatus.OPEN


def test_resolved_review_is_read_only(staff: Client, review: LicenceReview) -> None:
    """Once resolved, a review is part of the audit trail and cannot be changed."""
    url = reverse("admin:corpus_licencereview_change", args=[review.pk])
    staff.post(url, {"decision": "reject", "licence": "", "note": "No licence found."})
    review.refresh_from_db()
    assert review.status == ReviewStatus.REJECTED
    assert (
        staff.post(url, {"decision": "approve", "licence": "CC BY", "note": "x"}).status_code == 403
    )


def test_pgvector_extension_is_installed() -> None:
    """The first migration enables pgvector."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        row = cursor.fetchone()
    assert row is not None
    assert row[0]


def test_models_and_migrations_agree() -> None:
    """No model change is missing a migration."""
    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())
