"""Tests for recommendation_service.py"""

from unittest.mock import Mock

import pytest
from qdrant_client.models import PointStruct, Record, ScoredPoint

from app.services.recommendation_service import get_similar_resources


def test_get_similar_resources_success(mock_qdrant_client):
    """Test successful similar resource retrieval"""
    # Setup - mock retrieve to return the source point
    source_point = Record(
        id="source-point-id",
        payload={
            "text": "Source text",
            "metadata": {"resource_id": "123", "chunk_index": 0},
        },
        vector=None,
    )
    mock_qdrant_client.retrieve.return_value = [source_point]

    # Mock scroll to return chunks of the source resource
    mock_qdrant_client.scroll.return_value = ([source_point], None)

    # Mock query_points to return similar chunks
    similar_points = [
        ScoredPoint(
            id="similar-1-chunk-0",
            score=0.9,
            version=1,
            payload={
                "title": "Similar Resource 1",
                "metadata": {"resource_id": "456", "chunk_index": 0},
            },
        ),
        ScoredPoint(
            id="similar-2-chunk-0",
            score=0.8,
            version=1,
            payload={
                "title": "Similar Resource 2",
                "metadata": {"resource_id": "789", "chunk_index": 0},
            },
        ),
    ]
    mock_qdrant_client.query_points.return_value = Mock(points=similar_points)

    # Execute
    results = get_similar_resources(
        qdrant_client=mock_qdrant_client,
        vector_id="source-point-id",
        limit=5,
    )

    # Verify
    assert len(results) == 2
    assert results[0]["resource_id"] == "456"
    assert results[0]["score"] == 0.9
    assert results[0]["title"] == "Similar Resource 1"
    assert results[1]["resource_id"] == "789"


def test_get_similar_resources_point_not_found(mock_qdrant_client):
    """Test when source point is not found"""
    # Setup - retrieve returns empty
    mock_qdrant_client.retrieve.return_value = []

    # Execute
    results = get_similar_resources(
        qdrant_client=mock_qdrant_client,
        vector_id="nonexistent-id",
        limit=5,
    )

    # Verify
    assert results == []
    mock_qdrant_client.retrieve.assert_called_once()


def test_get_similar_resources_no_resource_id(mock_qdrant_client):
    """Test when source point has no resource_id in metadata"""
    # Setup - point without resource_id
    source_point = Record(
        id="source-id",
        payload={"text": "Source", "metadata": {}},  # No resource_id
        vector=None,
    )
    mock_qdrant_client.retrieve.return_value = [source_point]

    # Execute
    results = get_similar_resources(
        qdrant_client=mock_qdrant_client,
        vector_id="source-id",
        limit=5,
    )

    # Verify
    assert results == []


def test_get_similar_resources_excludes_source_resource(mock_qdrant_client):
    """Test that chunks from source resource are filtered out"""
    # Setup
    source_point = Record(
        id="source-id",
        payload={"metadata": {"resource_id": "123", "chunk_index": 0}},
        vector=None,
    )
    mock_qdrant_client.retrieve.return_value = [source_point]
    mock_qdrant_client.scroll.return_value = ([source_point], None)

    # Mock query returns both source resource chunks and similar resource chunks
    query_results = [
        ScoredPoint(
            id="source-chunk-1",
            score=1.0,
            version=1,
            payload={"title": "Source", "metadata": {"resource_id": "123", "chunk_index": 1}},
        ),  # Same resource
        ScoredPoint(
            id="similar-chunk-0",
            score=0.9,
            version=1,
            payload={"title": "Similar", "metadata": {"resource_id": "456", "chunk_index": 0}},
        ),  # Different resource
    ]
    mock_qdrant_client.query_points.return_value = Mock(points=query_results)

    # Execute
    results = get_similar_resources(
        qdrant_client=mock_qdrant_client,
        vector_id="source-id",
        limit=5,
    )

    # Verify only similar resource is returned (source filtered out)
    assert len(results) == 1
    assert results[0]["resource_id"] == "456"


def test_get_similar_resources_deduplicates_by_resource(mock_qdrant_client):
    """Test that multiple chunks from same resource are deduplicated"""
    # Setup
    source_point = Record(
        id="source-id",
        payload={"metadata": {"resource_id": "123", "chunk_index": 0}},
        vector=None,
    )
    mock_qdrant_client.retrieve.return_value = [source_point]
    mock_qdrant_client.scroll.return_value = ([source_point], None)

    # Mock query returns multiple chunks from same resource
    query_results = [
        ScoredPoint(
            id="similar-456-chunk-0",
            score=0.95,
            version=1,
            payload={"title": "Similar Doc", "metadata": {"resource_id": "456", "chunk_index": 0}},
        ),
        ScoredPoint(
            id="similar-456-chunk-1",
            score=0.90,
            version=1,
            payload={"title": "Similar Doc", "metadata": {"resource_id": "456", "chunk_index": 1}},
        ),
        ScoredPoint(
            id="similar-456-chunk-2",
            score=0.85,
            version=1,
            payload={"title": "Similar Doc", "metadata": {"resource_id": "456", "chunk_index": 2}},
        ),
    ]
    mock_qdrant_client.query_points.return_value = Mock(points=query_results)

    # Execute
    results = get_similar_resources(
        qdrant_client=mock_qdrant_client,
        vector_id="source-id",
        limit=5,
    )

    # Verify only one result per resource (highest score kept)
    assert len(results) == 1
    assert results[0]["resource_id"] == "456"
    assert results[0]["score"] == 0.95  # Highest score
    assert results[0]["vector_id"] == "similar-456-chunk-0"  # First chunk's vector ID used


def test_get_similar_resources_respects_limit(mock_qdrant_client):
    """Test that limit parameter is respected"""
    # Setup
    source_point = Record(
        id="source-id",
        payload={"metadata": {"resource_id": "123", "chunk_index": 0}},
        vector=None,
    )
    mock_qdrant_client.retrieve.return_value = [source_point]
    mock_qdrant_client.scroll.return_value = ([source_point], None)

    # Create 10 unique resources
    query_results = [
        ScoredPoint(
            id=f"similar-{i}-chunk-0",
            score=0.95 - i * 0.05,
            version=1,
            payload={"title": f"Doc {i}", "metadata": {"resource_id": str(i), "chunk_index": 0}},
        )
        for i in range(10)
    ]
    mock_qdrant_client.query_points.return_value = Mock(points=query_results)

    # Execute with limit=3
    results = get_similar_resources(
        qdrant_client=mock_qdrant_client,
        vector_id="source-id",
        limit=3,
    )

    # Verify only 3 results returned (top scoring)
    assert len(results) == 3
    assert results[0]["resource_id"] == "0"
    assert results[1]["resource_id"] == "1"
    assert results[2]["resource_id"] == "2"
