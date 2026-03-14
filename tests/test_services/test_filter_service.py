"""Tests for filter service."""

import pytest

from app.services.filter_service import build_qdrant_filter


class TestFilterService:
    """Test the filter service."""

    def test_build_filter_with_single_category(self):
        """Test building filter with single category in list."""
        filters = {"categories": ["tipsheet"]}
        result = build_qdrant_filter(filters)

        assert result is not None
        assert hasattr(result, "must")
        assert len(result.must) == 1
        assert result.must[0].key == "metadata.category"
        # Should use MatchAny for list values
        assert hasattr(result.must[0].match, "any")
        assert result.must[0].match.any == ["tipsheet"]

    def test_build_filter_with_multiple_categories(self):
        """Test building filter with multiple categories."""
        filters = {"categories": ["tipsheet", "audio"]}
        result = build_qdrant_filter(filters)

        assert result is not None
        assert len(result.must) == 1
        assert result.must[0].key == "metadata.category"
        # Should use MatchAny for multiple categories
        assert hasattr(result.must[0].match, "any")
        assert set(result.must[0].match.any) == {"tipsheet", "audio"}

    def test_build_filter_with_empty_categories_list(self):
        """Test building filter with empty categories list."""
        filters = {"categories": []}
        result = build_qdrant_filter(filters)

        # Empty list should not create a filter
        assert result is None

    def test_build_filter_with_none_categories(self):
        """Test building filter with None categories."""
        filters = {"categories": None}
        result = build_qdrant_filter(filters)

        # None should not create a filter
        assert result is None

    def test_build_filter_with_empty_dict(self):
        """Test building filter with empty dictionary."""
        result = build_qdrant_filter({})
        assert result is None

    def test_build_filter_preserves_case(self):
        """Test that filter preserves category case."""
        filters = {"categories": ["Tipsheet"]}
        result = build_qdrant_filter(filters)

        assert result is not None
        assert result.must[0].match.any == ["Tipsheet"]
