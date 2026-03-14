"""Diagnostic logging for debugging search result divergence between environments.

USAGE:
1. Set environment variable SEARCH_DIAGNOSTICS=1 to enable
2. Run the same query on both dev and prod
3. Compare the diagnostic output to find divergence point

To enable: set environment variable SEARCH_DIAGNOSTICS=1
"""

import hashlib
import os
from typing import Any

import structlog

# Diagnostics enabled by default - set SEARCH_DIAGNOSTICS=0 to disable
DIAGNOSTICS_ENABLED = os.getenv("SEARCH_DIAGNOSTICS", "1") == "1"

logger = structlog.get_logger("diagnostics")


def _log(stage: str, data: dict[str, Any]) -> None:
    """Log diagnostic entry using structlog."""
    if not DIAGNOSTICS_ENABLED:
        return

    logger.info("search_diagnostic", stage=stage, **data)


def log_environment_info() -> None:
    """Log environment and version information. Call once at startup."""
    if not DIAGNOSTICS_ENABLED:
        return

    versions: dict[str, str] = {}

    # ONNX Runtime version
    try:
        import onnxruntime  # type: ignore[import-untyped]

        versions["onnxruntime"] = onnxruntime.__version__
    except ImportError:
        versions["onnxruntime"] = "NOT_INSTALLED"

    # Sentence Transformers version
    try:
        import sentence_transformers

        versions["sentence_transformers"] = sentence_transformers.__version__
    except ImportError:
        versions["sentence_transformers"] = "NOT_INSTALLED"

    # fastembed version
    try:
        import fastembed

        versions["fastembed"] = getattr(fastembed, "__version__", "UNKNOWN")
    except ImportError:
        versions["fastembed"] = "NOT_INSTALLED"

    # Qdrant client version
    try:
        import qdrant_client

        versions["qdrant_client"] = getattr(qdrant_client, "__version__", "UNKNOWN")
    except ImportError:
        versions["qdrant_client"] = "NOT_INSTALLED"

    # NumPy version (affects floating point)
    try:
        import numpy

        versions["numpy"] = numpy.__version__
    except ImportError:
        versions["numpy"] = "NOT_INSTALLED"

    # Python version
    import platform
    import sys

    versions["python"] = sys.version.split()[0]

    # Platform info
    versions["platform"] = platform.platform()
    versions["processor"] = platform.processor()

    _log("environment", {"versions": versions})


def log_collection_info(client: Any, collection_name: str) -> None:
    """Log collection statistics."""
    if not DIAGNOSTICS_ENABLED:
        return

    try:
        info = client.get_collection(collection_name)
        _log(
            "collection",
            {
                "name": collection_name,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": str(info.status),
            },
        )
    except Exception as e:
        _log("collection", {"error": str(e)})


def log_query_input(query: str, filters: dict[str, Any] | None, limit: int, offset: int, sort_by: str) -> None:
    """Log the incoming search request without storing raw query text."""
    if not DIAGNOSTICS_ENABLED:
        return

    _log(
        "query_input",
        {
            "query_hash": hashlib.md5(query.encode()).hexdigest()[:8],
            "query_length": len(query),
            "filters": filters,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
        },
    )


def log_dense_embedding(query: str, embedding: list[float]) -> None:
    """Log dense embedding statistics for comparison."""
    if not DIAGNOSTICS_ENABLED:
        return

    import numpy as np

    emb_array = np.array(embedding)

    # Compute fingerprint - hash of rounded values for comparison
    rounded = np.round(emb_array, decimals=4)
    fingerprint = hashlib.md5(rounded.tobytes()).hexdigest()[:16]

    _log(
        "dense_embedding",
        {
            "query_hash": hashlib.md5(query.encode()).hexdigest()[:8],
            "dimensions": len(embedding),
            "min": float(np.min(emb_array)),
            "max": float(np.max(emb_array)),
            "mean": float(np.mean(emb_array)),
            "std": float(np.std(emb_array)),
            "l2_norm": float(np.linalg.norm(emb_array)),
            "first_5": [round(x, 6) for x in embedding[:5]],
            "last_5": [round(x, 6) for x in embedding[-5:]],
            "fingerprint": fingerprint,
        },
    )


def log_sparse_embedding(query: str, sparse_embedding: Any) -> None:
    """Log sparse embedding statistics."""
    if not DIAGNOSTICS_ENABLED:
        return

    try:
        # fastembed sparse embedding structure
        indices = list(sparse_embedding.indices) if hasattr(sparse_embedding, "indices") else []
        values = list(sparse_embedding.values) if hasattr(sparse_embedding, "values") else []

        _log(
            "sparse_embedding",
            {
                "query_hash": hashlib.md5(query.encode()).hexdigest()[:8],
                "num_terms": len(indices),
                "indices_sample": indices[:10] if indices else [],
                "values_sample": [round(v, 4) for v in values[:10]] if values else [],
                "max_value": round(max(values), 4) if values else 0,
                "sum_values": round(sum(values), 4) if values else 0,
            },
        )
    except Exception as e:
        _log("sparse_embedding", {"error": str(e)})


def log_fusion_results(results: list[Any], stage: str = "rrf_fusion") -> None:
    """Log results after RRF fusion."""
    if not DIAGNOSTICS_ENABLED:
        return

    if not results:
        _log(stage, {"count": 0})
        return

    scores = [getattr(r, "score", 0) for r in results if getattr(r, "score", None) is not None]

    _log(
        stage,
        {
            "count": len(results),
            "score_min": round(min(scores), 6) if scores else None,
            "score_max": round(max(scores), 6) if scores else None,
            "score_mean": round(sum(scores) / len(scores), 6) if scores else None,
        },
    )


def log_reranking(
    query: str,
    input_count: int,
    output_count: int,
    min_score_threshold: float | None,
    scores_before: list[float],
    scores_after: list[float],
    filtered_count: int,
) -> None:
    """Log reranking stage details."""
    if not DIAGNOSTICS_ENABLED:
        return

    _log(
        "reranking",
        {
            "query_hash": hashlib.md5(query.encode()).hexdigest()[:8],
            "input_count": input_count,
            "output_count": output_count,
            "filtered_by_min_score": filtered_count,
            "min_score_threshold": min_score_threshold,
            "scores_before_min": round(min(scores_before), 4) if scores_before else None,
            "scores_before_max": round(max(scores_before), 4) if scores_before else None,
            "scores_after_min": round(min(scores_after), 4) if scores_after else None,
            "scores_after_max": round(max(scores_after), 4) if scores_after else None,
        },
    )


def log_final_results(
    results: list[Any],
    total_count: int,
    deduplicated_count: int,
) -> None:
    """Log final results being returned."""
    if not DIAGNOSTICS_ENABLED:
        return

    _log(
        "final_results",
        {
            "returned_count": len(results),
            "total_count": total_count,
            "deduplicated": deduplicated_count,
        },
    )


def log_stage_summary(stages: dict[str, int]) -> None:
    """Log a summary of counts at each stage for easy comparison."""
    if not DIAGNOSTICS_ENABLED:
        return

    _log("pipeline_summary", stages)


class SearchDiagnostics:
    """Context manager for tracking search pipeline diagnostics."""

    def __init__(self, query: str, filters: dict[str, Any] | None = None):
        self.query = query
        self.filters = filters
        self.stages: dict[str, int] = {}
        self.enabled = DIAGNOSTICS_ENABLED

    def record(self, stage: str, count: int) -> None:
        """Record count at a pipeline stage."""
        self.stages[stage] = count

    def summary(self) -> None:
        """Print summary of all stages."""
        if self.enabled:
            log_stage_summary(self.stages)
