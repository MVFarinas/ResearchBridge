"""Validation of API inputs (query parameters and request bodies)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from rb_backend.identifiers import MAX_QUERY_LENGTH

MIN_YEAR = 1600
MAX_YEAR = 2100
MAX_PAGE = 50


class SearchParamsSerializer(serializers.Serializer[dict[str, Any]]):
    """Query parameters of ``GET /api/v1/search/``."""

    q = serializers.CharField(max_length=300, trim_whitespace=True)
    year_from = serializers.IntegerField(min_value=MIN_YEAR, max_value=MAX_YEAR, required=False)
    year_to = serializers.IntegerField(min_value=MIN_YEAR, max_value=MAX_YEAR, required=False)
    availability = serializers.ChoiceField(
        choices=["plain_english_available", "original_annotations_only"], required=False
    )
    type = serializers.MultipleChoiceField(
        choices=["article", "review", "preprint"], required=False
    )
    sort = serializers.ChoiceField(choices=["relevance", "newest", "oldest"], default="relevance")
    page = serializers.IntegerField(min_value=1, max_value=MAX_PAGE, default=1)
    openalex = serializers.BooleanField(default=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Check that the year range is not reversed.

        Args:
            attrs: The field values.

        Returns:
            The values unchanged.

        Raises:
            serializers.ValidationError: If ``year_from`` is after ``year_to``.
        """
        year_from, year_to = attrs.get("year_from"), attrs.get("year_to")
        if year_from is not None and year_to is not None and year_from > year_to:
            raise serializers.ValidationError("year_from must not be after year_to")
        return attrs


class LookupSerializer(serializers.Serializer[dict[str, Any]]):
    """Body of ``POST /api/v1/lookup/``."""

    query = serializers.CharField(max_length=MAX_QUERY_LENGTH, trim_whitespace=True)
