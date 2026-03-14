"""Tests for search endpoint."""

from unittest.mock import Mock, patch

import pytest
from qdrant_client.models import ScoredPoint


class TestSearchEndpoint:
    """Test the /search endpoint."""

    def test_search_with_query_success(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test successful semantic search with query."""
        # Mock the query_points response
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        response = client.post(
            "/search",
            json={
                "query": "data journalism tips",
                "limit": 10,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == "data journalism tips"
        assert data["count"] == 2
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert len(data["results"]) == 2

        # Verify first result structure
        result = data["results"][0]
        assert result["vector_id"] == "test-uuid-1"
        assert result["title"] == "Test Resource 1"
        # Score is from cross-encoder reranking (0.9), not original hybrid score (0.95)
        assert result["score"] == 0.9
        assert "metadata" in result

    def test_search_filter_only_browse_mode(self, client, mock_qdrant_client, sample_search_results):
        """Test filter-only browse mode (no query, only categories filter)."""
        # Mock scroll response for filter-only mode - must return all matching records
        # The scroll method will be called repeatedly until it returns None as offset
        # For this test, we return all results in first call with None offset
        mock_qdrant_client.scroll.return_value = (sample_search_results, None)

        response = client.post(
            "/search",
            json={
                "categories": ["tipsheet"],
                "limit": 10,
                "offset": 0,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["query"] == ""
        assert data["count"] == 2
        # Total should equal the number of results from scroll (all matching records)
        assert data["total"] == 2

    def test_search_with_pagination(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test search with pagination parameters."""
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        response = client.post(
            "/search",
            json={
                "query": "test query",
                "limit": 5,
                "offset": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 5
        assert data["offset"] == 10

    def test_search_with_sort_by_newest(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test search with sort_by=newest."""
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        response = client.post(
            "/search",
            json={
                "query": "test query",
                "sort_by": "newest",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_search_with_sort_by_oldest(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test search with sort_by=oldest."""
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        response = client.post(
            "/search",
            json={
                "query": "test query",
                "sort_by": "oldest",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_search_invalid_limit_too_high(self, client):
        """Test search with limit above maximum (100)."""
        response = client.post(
            "/search",
            json={
                "query": "test query",
                "limit": 101,  # Max is 100
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "limit" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_invalid_limit_zero(self, client):
        """Test search with zero limit."""
        response = client.post(
            "/search",
            json={
                "query": "test query",
                "limit": 0,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "limit" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_invalid_offset_negative(self, client):
        """Test search with negative offset parameter."""
        response = client.post(
            "/search",
            json={
                "query": "test query",
                "offset": -1,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "offset" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_invalid_offset_too_high(self, client):
        """Test search with offset above maximum (10000)."""
        response = client.post(
            "/search",
            json={
                "query": "test query",
                "offset": 10001,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "offset" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_invalid_sort_by(self, client):
        """Test search with invalid sort_by parameter."""
        response = client.post(
            "/search",
            json={
                "query": "test query",
                "sort_by": "invalid",
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "sort_by" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_no_query_no_category(self, client):
        """Test search with neither query nor category filter."""
        response = client.post(
            "/search",
            json={
                "limit": 10,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        # Should contain validation error about requiring query or category
        assert "query" in data["message"].lower() or "category" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_empty_query_string(self, client):
        """Test search with empty query string and no category raises error."""
        response = client.post(
            "/search",
            json={
                "query": "   ",
                "limit": 10,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        # Should require either query or category
        assert "query" in data["message"].lower() or "category" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_invalid_category(self, client):
        """Test search with invalid category."""
        response = client.post(
            "/search",
            json={
                "query": "test query",
                "categories": ["invalid_category"],
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "categories" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_query_too_long(self, client):
        """Test search with query exceeding max length."""
        long_query = "a" * 1001  # MAX_QUERY_LENGTH is 1000

        response = client.post(
            "/search",
            json={
                "query": long_query,
                "limit": 10,
            },
        )

        assert response.status_code == 422  # Pydantic validation error
        data = response.json()
        assert data["error"] == "VALIDATION_ERROR"
        assert "query" in data["message"].lower()
        assert data["status_code"] == 422
        assert "request_id" in data

    def test_search_with_category_filter(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test search with categories filter."""
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        response = client.post(
            "/search",
            json={
                "query": "test query",
                "categories": ["tipsheet"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_search_with_category_all(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test search with categories=['all'] (should not filter)."""
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        response = client.post(
            "/search",
            json={
                "query": "test query",
                "categories": ["all"],
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    def test_search_caching(self, client, mock_qdrant_client, sample_search_results, mock_cross_encoder):
        """Test that search results are cached."""
        mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

        # First request
        response1 = client.post(
            "/search",
            json={
                "query": "cached query",
                "limit": 10,
            },
        )

        # Second identical request should hit cache
        response2 = client.post(
            "/search",
            json={
                "query": "cached query",
                "limit": 10,
            },
        )

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

        # Verify Qdrant was only called once (cached on second call)
        assert mock_qdrant_client.query_points.call_count == 1

    def test_search_duplicate_removal(self, client, mock_qdrant_client, mock_cross_encoder):
        """Test that duplicate results are removed."""
        # Create results with duplicate IDs
        duplicate_results = [
            ScoredPoint(
                id="test-uuid-1",
                score=0.95,
                payload={
                    "title": "Test Resource 1",
                    "text": "Test content",
                    "doc_type": "tipsheet",
                    "metadata": {"resource_id": "12345"},
                },
                version=1,
            ),
            ScoredPoint(
                id="test-uuid-1",  # Duplicate ID
                score=0.90,
                payload={
                    "title": "Test Resource 1",
                    "text": "Test content",
                    "doc_type": "tipsheet",
                    "metadata": {"resource_id": "12345"},
                },
                version=1,
            ),
        ]

        mock_qdrant_client.query_points.return_value = Mock(points=duplicate_results)

        response = client.post(
            "/search",
            json={
                "query": "test query",
                "limit": 10,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Should only have 1 result (duplicates removed)
        assert data["count"] == 1
        assert len(data["results"]) == 1
