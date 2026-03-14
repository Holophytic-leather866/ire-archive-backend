"""Tests for cache_service.py"""

import pytest

from app.services.cache_service import (
    get_rerank_cache_key,
    reranked_cache,
    reranked_cache_metrics,
)


def test_get_rerank_cache_key_basic():
    """Test cache key generation with basic parameters"""
    key = get_rerank_cache_key("test query", None, "relevance")

    # Key should be consistent for same inputs
    key2 = get_rerank_cache_key("test query", None, "relevance")
    assert key == key2


def test_get_rerank_cache_key_with_filters():
    """Test cache key generation with filters"""
    filters = {"category": "tipsheet"}
    key = get_rerank_cache_key("test query", filters, "relevance")

    # Different filters should produce different keys
    filters2 = {"category": "journal"}
    key2 = get_rerank_cache_key("test query", filters2, "relevance")
    assert key != key2


def test_get_rerank_cache_key_with_sort():
    """Test cache key generation with different sort modes"""
    key_relevance = get_rerank_cache_key("test query", None, "relevance")
    key_newest = get_rerank_cache_key("test query", None, "newest")
    key_oldest = get_rerank_cache_key("test query", None, "oldest")

    # Different sort modes should produce different keys
    assert key_relevance != key_newest
    assert key_relevance != key_oldest
    assert key_newest != key_oldest


def test_get_rerank_cache_key_query_case_sensitive():
    """Test that cache keys are case-sensitive for queries"""
    key1 = get_rerank_cache_key("Test Query", None, "relevance")
    key2 = get_rerank_cache_key("test query", None, "relevance")

    # Different cases should produce different keys
    assert key1 != key2


def test_reranked_cache_is_dict():
    """Test that reranked_cache is accessible and behaves like a dict"""
    from cachetools import TTLCache

    # reranked_cache is a TTLCache which inherits from dict-like interface
    assert isinstance(reranked_cache, TTLCache)
    # Verify it has dict-like methods
    assert hasattr(reranked_cache, "__getitem__")
    assert hasattr(reranked_cache, "__setitem__")
    assert hasattr(reranked_cache, "clear")


def test_reranked_cache_metrics_structure():
    """Test that cache metrics has correct structure"""
    assert "hits" in reranked_cache_metrics
    assert "misses" in reranked_cache_metrics
    assert isinstance(reranked_cache_metrics["hits"], int)
    assert isinstance(reranked_cache_metrics["misses"], int)
