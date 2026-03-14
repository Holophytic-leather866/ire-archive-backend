"""Tests for search_service.py"""

from unittest.mock import AsyncMock, Mock

import pytest
from qdrant_client.models import PointStruct, Record, ScoredPoint

from app.services.search_service import (
    format_search_results,
    perform_filter_only_search,
    perform_semantic_search,
)


def test_perform_semantic_search_success(
    mock_qdrant_client,
    mock_embedding_model,
    mock_sparse_model,
    sample_search_results,
):
    """Test successful semantic search with query"""
    # Setup mock
    mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)

    # Execute
    results, total = perform_semantic_search(
        qdrant_client=mock_qdrant_client,
        embedding_model=mock_embedding_model,
        sparse_model=mock_sparse_model,
        query="test query",
        limit=10,
        offset=0,
        sort_by="relevance",
        qdrant_filter=None,
    )

    # Verify
    assert len(results) == 2
    assert total == 2
    assert results[0].id == "test-uuid-1"
    assert results[1].id == "test-uuid-2"

    # Verify embedding models were called
    mock_embedding_model.encode.assert_called_once_with("test query")
    # Sparse model was called (embed method returns generator/iterable)
    mock_sparse_model.embed.assert_called_once_with(["test query"])


def test_perform_semantic_search_with_filters(
    mock_qdrant_client,
    mock_embedding_model,
    mock_sparse_model,
    sample_search_results,
):
    """Test semantic search with filter"""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    # Setup
    mock_qdrant_client.query_points.return_value = Mock(points=sample_search_results)
    test_filter = Filter(must=[FieldCondition(key="metadata.category", match=MatchValue(value="tipsheet"))])

    # Execute with filter
    results, total = perform_semantic_search(
        qdrant_client=mock_qdrant_client,
        embedding_model=mock_embedding_model,
        sparse_model=mock_sparse_model,
        query="test query",
        limit=10,
        offset=0,
        sort_by="relevance",
        qdrant_filter=test_filter,
    )

    # Verify filter was applied
    assert len(results) == 2
    call_kwargs = mock_qdrant_client.query_points.call_args.kwargs
    assert "query_filter" in call_kwargs
    assert call_kwargs["query_filter"] == test_filter


def test_perform_semantic_search_pagination(
    mock_qdrant_client,
    mock_embedding_model,
    mock_sparse_model,
):
    """Test pagination returns correct slice of results"""
    # Setup - create 5 results
    all_results = [
        ScoredPoint(id=f"id-{i}", score=0.9 - i * 0.1, version=1, payload={"text": f"text {i}"}) for i in range(5)
    ]
    mock_qdrant_client.query_points.return_value = Mock(points=all_results)

    # Execute with offset=2, limit=2 (should get items 2 and 3)
    results, total = perform_semantic_search(
        qdrant_client=mock_qdrant_client,
        embedding_model=mock_embedding_model,
        sparse_model=mock_sparse_model,
        query="test query",
        limit=2,
        offset=2,
        sort_by="relevance",
        qdrant_filter=None,
    )

    # Verify pagination
    assert len(results) == 2
    assert total == 5
    assert results[0].id == "id-2"
    assert results[1].id == "id-3"


def test_perform_filter_only_search_browse_mode(
    mock_qdrant_client,
    sample_search_results,
):
    """Test filter-only search without semantic query (browse mode)"""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    # Setup
    mock_qdrant_client.scroll.return_value = (sample_search_results, None)
    test_filter = Filter(must=[FieldCondition(key="metadata.category", match=MatchValue(value="tipsheet"))])

    # Execute browse mode (no query, only filters)
    results, total = perform_filter_only_search(
        qdrant_client=mock_qdrant_client,
        qdrant_filter=test_filter,
        limit=10,
        offset=0,
        sort_by="relevance",
    )

    # Verify
    assert len(results) == 2
    assert total == 2
    assert results[0].id == "test-uuid-1"

    # Verify scroll was called (not query_points)
    mock_qdrant_client.scroll.assert_called()
    call_kwargs = mock_qdrant_client.scroll.call_args.kwargs
    assert "scroll_filter" in call_kwargs
    assert call_kwargs["scroll_filter"] == test_filter


def test_perform_filter_only_search_pagination(
    mock_qdrant_client,
):
    """Test pagination in filter-only search"""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    # Setup - create 5 results
    all_results = [Record(id=f"id-{i}", payload={"text": f"text {i}"}) for i in range(5)]
    mock_qdrant_client.scroll.return_value = (all_results, None)
    test_filter = Filter(must=[FieldCondition(key="metadata.category", match=MatchValue(value="tipsheet"))])

    # Execute with offset=1, limit=2
    results, total = perform_filter_only_search(
        qdrant_client=mock_qdrant_client,
        qdrant_filter=test_filter,
        limit=2,
        offset=1,
        sort_by="relevance",
    )

    # Verify pagination
    assert len(results) == 2
    assert total == 5
    assert results[0].id == "id-1"
    assert results[1].id == "id-2"


def test_format_search_results_scored_points(sample_search_results):
    """Test formatting ScoredPoint results"""
    formatted = format_search_results(sample_search_results)

    assert len(formatted) == 2
    assert formatted[0]["vector_id"] == "test-uuid-1"
    assert formatted[0]["score"] == 0.95
    assert formatted[0]["text"] == "This is a test resource about data journalism."
    assert formatted[0]["title"] == "Test Resource 1"
    assert formatted[0]["doc_type"] == "tipsheet"
    assert formatted[0]["metadata"]["category"] == "tipsheet"


def test_format_search_results_records():
    """Test formatting Record results (no scores)"""
    records = [
        Record(id="rec-1", payload={"text": "Record 1", "title": "Title 1", "doc_type": "journal"}),
        Record(id="rec-2", payload={"text": "Record 2", "title": "Title 2", "doc_type": "audio"}),
    ]

    formatted = format_search_results(records)

    assert len(formatted) == 2
    assert formatted[0]["vector_id"] == "rec-1"
    assert formatted[0]["score"] == 1.0  # Default score for Record
    assert formatted[0]["text"] == "Record 1"
    assert formatted[0]["title"] == "Title 1"


def test_format_search_results_handles_missing_payload():
    """Test formatting handles missing payload gracefully"""
    results = [
        ScoredPoint(id="no-payload", score=0.8, version=1, payload=None),
    ]

    formatted = format_search_results(results)

    assert len(formatted) == 1
    assert formatted[0]["vector_id"] == "no-payload"
    assert formatted[0]["score"] == 0.8
    assert formatted[0]["text"] == ""
    assert formatted[0]["title"] == ""
    assert formatted[0]["metadata"] == {}


def test_format_search_results_deduplicates():
    """Test that duplicate IDs are removed (keeps first occurrence)"""
    results = [
        ScoredPoint(id="dup-id", score=0.95, version=1, payload={"text": "First"}),
        ScoredPoint(id="dup-id", score=0.85, version=1, payload={"text": "Second"}),
        ScoredPoint(id="unique-id", score=0.75, version=1, payload={"text": "Unique"}),
    ]

    formatted = format_search_results(results)

    assert len(formatted) == 2
    assert formatted[0]["vector_id"] == "dup-id"
    assert formatted[0]["text"] == "First"  # Keeps first occurrence
    assert formatted[1]["vector_id"] == "unique-id"
