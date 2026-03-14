"""Tests for resource endpoints."""

from unittest.mock import Mock

import pytest


class TestResourceEndpoint:
    """Test the /resource/{id} endpoint."""

    def test_get_resource_success(self, client, mock_qdrant_client, sample_point_record):
        """Test successful resource retrieval by UUID."""
        mock_qdrant_client.retrieve.return_value = [sample_point_record]

        response = client.get("/resource/test-uuid-1")

        assert response.status_code == 200
        data = response.json()

        # CRITICAL: Verify UUID is used as vector_id (not resource_id)
        assert data["vector_id"] == "test-uuid-1"
        assert data["title"] == "Test Resource 1"
        assert data["text"] == "This is a test resource about data journalism."
        assert data["doc_type"] == "tipsheet"
        assert "metadata" in data
        assert data["metadata"]["resource_id"] == "12345"

    def test_get_resource_not_found(self, client, mock_qdrant_client):
        """Test resource not found returns 404."""
        mock_qdrant_client.retrieve.return_value = []

        response = client.get("/resource/non-existent-uuid")

        assert response.status_code == 404
        data = response.json()
        # New standardized error format
        assert data["error"] == "NOT_FOUND"
        assert "Resource not found" in data["message"]
        assert data["status_code"] == 404
        assert "request_id" in data

    def test_get_resource_caching(self, client, mock_qdrant_client, sample_point_record):
        """Test that resource requests are cached."""
        mock_qdrant_client.retrieve.return_value = [sample_point_record]

        # First request
        response1 = client.get("/resource/test-uuid-1")

        # Second identical request should hit cache
        response2 = client.get("/resource/test-uuid-1")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

        # Verify Qdrant was only called once (cached on second call)
        assert mock_qdrant_client.retrieve.call_count == 1


class TestSimilarResourcesEndpoint:
    """Test the /resource/{id}/similar endpoint."""

    def test_get_similar_resources_success(self, client, mock_qdrant_client, sample_search_results):
        """Test successful similar resources retrieval."""
        # Mock retrieve for the source resource
        source_record = Mock()
        source_record.id = "test-uuid-1"
        source_record.vector = {"dense": [0.1] * 384}
        source_record.payload = {"metadata": {"resource_id": "12345"}}
        mock_qdrant_client.retrieve.return_value = [source_record]

        # Mock search for similar resources
        mock_qdrant_client.search.return_value = sample_search_results[:1]  # Return 1 similar

        response = client.get("/resource/test-uuid-1/similar")

        assert response.status_code == 200
        data = response.json()

        assert data["vector_id"] == "test-uuid-1"
        assert "similar_resources" in data
        assert data["count"] >= 0

    def test_get_similar_resources_not_found(self, client, mock_qdrant_client):
        """Test similar resources when source resource not found."""
        mock_qdrant_client.retrieve.return_value = []

        response = client.get("/resource/non-existent-uuid/similar")

        assert response.status_code == 404

    def test_get_similar_resources_caching(self, client, mock_qdrant_client, sample_search_results):
        """Test that similar resources are cached."""
        # Mock retrieve for the source resource
        source_record = Mock()
        source_record.id = "test-uuid-1"
        source_record.vector = {"dense": [0.1] * 384}
        source_record.payload = {"metadata": {"resource_id": "12345"}}
        mock_qdrant_client.retrieve.return_value = [source_record]

        # Mock scroll for finding chunks of the current resource
        mock_qdrant_client.scroll.return_value = ([source_record], None)

        # Mock query_points for finding similar resources
        mock_query_result = Mock()
        mock_query_result.points = sample_search_results[:1]
        mock_qdrant_client.query_points.return_value = mock_query_result

        # First request
        response1 = client.get("/resource/test-uuid-1/similar")

        # Second identical request should hit cache
        response2 = client.get("/resource/test-uuid-1/similar")

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.json() == response2.json()

        # Verify Qdrant query_points was only called once (cached on second call)
        assert mock_qdrant_client.query_points.call_count == 1

    def test_similar_resources_exclude_self(self, client, mock_qdrant_client, sample_search_results):
        """Test that similar resources exclude the source resource itself."""
        # Mock retrieve for the source resource
        source_record = Mock()
        source_record.id = "test-uuid-1"
        source_record.vector = {"dense": [0.1] * 384}
        source_record.payload = {"metadata": {"resource_id": "12345"}}
        mock_qdrant_client.retrieve.return_value = [source_record]

        # Mock search returns the source resource (should be filtered out)
        mock_qdrant_client.search.return_value = sample_search_results
