"""Unit tests for input validators."""

import pytest

from app.validators import MAX_OFFSET, MAX_QUERY_LENGTH, sanitize_query


class TestSanitizeQuery:
    """Tests for sanitize_query function."""

    def test_valid_query(self):
        """Test sanitization with valid query."""
        result = sanitize_query("test query")
        assert result == "test query"

    def test_none_query(self):
        """Test sanitization with None returns None."""
        result = sanitize_query(None)
        assert result is None

    def test_strips_whitespace(self):
        """Test query whitespace is stripped."""
        result = sanitize_query("  test query  ")
        assert result == "test query"

    def test_empty_string_returns_none(self):
        """Test empty string returns None (allows filter-only browsing)."""
        result = sanitize_query("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        """Test whitespace-only string returns None (allows filter-only browsing)."""
        result = sanitize_query("   ")
        assert result is None

    def test_preserves_internal_whitespace(self):
        """Test internal whitespace is preserved."""
        result = sanitize_query("  multiple   spaces   inside  ")
        assert result == "multiple   spaces   inside"


class TestConstants:
    """Tests for validator constants."""

    def test_max_query_length(self):
        """Test MAX_QUERY_LENGTH is set correctly."""
        assert MAX_QUERY_LENGTH == 1000

    def test_max_offset(self):
        """Test MAX_OFFSET is set correctly."""
        assert MAX_OFFSET == 10000
