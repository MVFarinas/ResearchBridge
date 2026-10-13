"""API views: paper detail, credibility, search, lookup and lookup status.

All endpoints are public and unauthenticated (Plan.md M2: read-only, no
accounts). Each has a throttle scope whose rate comes from settings
(``RB_API_RATE_*``). Metadata clients and the PMC bucket are module-level
factories so tests can substitute clients that serve recorded responses.
"""

from __future__ import annotations

import uuid

from django.http import Http404
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from rb_backend.api.papers import paper_detail
from rb_backend.api.serializers import LookupSerializer, SearchParamsSerializer
from rb_backend.corpus.models import Paper
from rb_backend.discovery.keys import find_displayable_paper
from rb_backend.discovery.lookup import LookupOutcome, lookup, request_status
from rb_backend.discovery.models import LookupRequest
from rb_backend.discovery.search import SearchParams, run_search
from rb_backend.identifiers import IdentifierError
from rb_backend.ingestion.runtime import get_request_bucket
from rb_backend.metadata.credibility import paper_credibility
from rb_backend.metadata.services import default_clients

# Factories, replaced in tests.
metadata_clients = default_clients
pmc_bucket = get_request_bucket


class _PublicView(APIView):
    """Base for the public endpoints: no authentication, scoped throttling."""

    authentication_classes = ()
    permission_classes = ()
    throttle_classes = (ScopedRateThrottle,)


def _paper_or_404(key: str) -> Paper:
    """Resolve a paper key to a displayable paper.

    Args:
        key: The public key.

    Returns:
        The paper.

    Raises:
        Http404: If no displayable paper has that key.
    """
    paper = find_displayable_paper(key)
    if paper is None:
        raise Http404("no displayable paper with that key")
    return paper


class PaperDetailView(_PublicView):
    """``GET /api/v1/papers/<key>/``: the paper page's content."""

    throttle_scope = "papers"

    def get(self, request: Request, key: str) -> Response:
        """Return the paper's detail document.

        Args:
            request: The request.
            key: The paper key.

        Returns:
            200 with the document, or 404.
        """
        detail = paper_detail(_paper_or_404(key))
        if detail is None:
            raise Http404("no displayable version")
        return Response(detail)


class PaperCredibilityView(_PublicView):
    """``GET /api/v1/papers/<key>/credibility/``: neutral, paper-level signals."""

    throttle_scope = "credibility"

    def get(self, request: Request, key: str) -> Response:
        """Return the paper's credibility signals with their "as of" dates.

        Args:
            request: The request.
            key: The paper key.

        Returns:
            200 with the signals (sections may report a source unavailable), or 404.
        """
        paper = _paper_or_404(key)
        return Response(paper_credibility(paper, metadata_clients()))


class SearchView(_PublicView):
    """``GET /api/v1/search/?q=...``: corpus and OpenAlex search."""

    throttle_scope = "search"

    def get(self, request: Request) -> Response:
        """Run a search.

        Args:
            request: The request; parameters are validated by
                :class:`SearchParamsSerializer`.

        Returns:
            200 with both result lists, or 400 for invalid parameters.
        """
        serializer = SearchParamsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        params = SearchParams(
            query=data["q"],
            year_from=data.get("year_from"),
            year_to=data.get("year_to"),
            availability=data.get("availability"),
            work_types=tuple(sorted(data.get("type") or ())),
            sort=data["sort"],
            page=data["page"],
            include_openalex=data["openalex"],
        )
        return Response(run_search(params, metadata_clients()))


class LookupView(_PublicView):
    """``POST /api/v1/lookup/`` with ``{"query": ...}``: find or prepare a paper."""

    throttle_scope = "lookup"

    def post(self, request: Request) -> Response:
        """Look a paper up; an eligible one is queued for ingestion.

        Args:
            request: The request.

        Returns:
            202 when queued, 503 when a source was unreachable, 400 for an
            unusable query, else 200; the body's ``outcome`` says which.
        """
        serializer = LookupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = lookup(
                serializer.validated_data["query"],
                metadata_clients(),
                bucket_factory=pmc_bucket,
            )
        except IdentifierError as exc:
            return Response({"query": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        codes = {
            LookupOutcome.QUEUED: status.HTTP_202_ACCEPTED,
            LookupOutcome.UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
        }
        return Response(result, status=codes.get(result["outcome"], status.HTTP_200_OK))


class LookupRequestView(_PublicView):
    """``GET /api/v1/lookup/requests/<id>/``: is the requested paper ready yet?"""

    throttle_scope = "lookup_status"

    def get(self, request: Request, request_id: uuid.UUID) -> Response:
        """Return a lookup request's status.

        Args:
            request: The request.
            request_id: The lookup request's UUID.

        Returns:
            200 with the status, or 404.
        """
        lookup_request = LookupRequest.objects.filter(pk=request_id).first()
        if lookup_request is None:
            raise Http404("no such lookup request")
        return Response(request_status(lookup_request))
