"""Cross-encoder reranking for improved search precision."""

import numpy as np
import structlog
from qdrant_client.models import ScoredPoint

from app.config import DEFAULT_LIMIT, MAX_RERANK_TEXT_LENGTH, RERANK_MIN_SCORE
from app.dependencies import get_reranker

logger = structlog.get_logger()


def rerank_results(query: str, results: list[ScoredPoint], limit: int) -> list[ScoredPoint]:
    """Rerank search results using cross-encoder for improved precision.

    Cross-encoders jointly encode query+document pairs, capturing semantic
    relationships that bi-encoders miss. This improves precision at the cost
    of additional latency (~200-500ms for 50 candidates).

    Args:
        query: Original search query text
        results: List of scored results from hybrid search
        limit: Maximum number of results to return

    Returns:
        Reranked list of results with updated cross-encoder scores

    Note:
        - Only reranks if we have at least 2 results
        - Truncates document text to 1000 chars for speed
        - Creates new ScoredPoint objects (doesn't modify originals)
        - Filters all scores below RERANK_MIN_SCORE after reranking
    """
    # Skip reranking if insufficient results
    if len(results) < 2:
        logger.info("skipping_reranking", result_count=len(results), reason="insufficient_results")
        return results

    logger.info("reranking_candidates", candidate_count=len(results))

    # Get reranker (initialized at startup)
    reranker = get_reranker()

    # Extract text for reranking (limit length for speed)
    documents = [
        result.payload.get("text", "")[:MAX_RERANK_TEXT_LENGTH] if result.payload else "" for result in results
    ]

    # Score all query-document pairs with cross-encoder
    pairs = [(query, doc) for doc in documents]
    rerank_scores = reranker.predict(pairs, batch_size=16)

    logger.info(
        "cross_encoder_scores",
        max_score=float(max(rerank_scores)),
        min_score=float(min(rerank_scores)),
        mean_score=float(np.mean(rerank_scores)),
        std_score=float(np.std(rerank_scores)),
    )

    # Pair results with their scores
    paired_results = list(zip(results, rerank_scores))

    # Filter out results below minimum score threshold
    filtered_results = [pr for pr in paired_results if pr[1] >= RERANK_MIN_SCORE]
    logger.info(
        "reranking_filtered",
        filtered_count=len(paired_results) - len(filtered_results),
        remaining_count=len(filtered_results),
        min_score=float(min(s for _r, s in filtered_results)) if filtered_results else None,
        max_score=float(max(s for _r, s in filtered_results)) if filtered_results else None,
    )

    # Sort by cross-encoder scores (descending) and take top limit
    reranked = sorted(filtered_results, key=lambda x: x[1], reverse=True)[:limit]

    # Create new ScoredPoint objects with updated scores
    # (Don't modify originals - they may be immutable)
    reranked_results = []
    for result, new_score in reranked:
        new_result = ScoredPoint(
            id=result.id,
            version=result.version,
            score=float(new_score),
            payload=result.payload,
            vector=result.vector,
        )
        reranked_results.append(new_result)

    if not reranked_results:
        logger.warning("all_results_filtered")
        return []

    logger.info(
        "reranking_complete",
        result_count=len(reranked_results),
        top_score=float(reranked_results[0].score),
        bottom_score=float(reranked_results[-1].score),
        mean_score=float(np.mean([r.score for r in reranked_results])),
        std_score=float(np.std([r.score for r in reranked_results])),
    )

    return reranked_results
