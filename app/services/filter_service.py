"""Filter operations service for Qdrant queries."""

from typing import Optional, cast

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue


def build_qdrant_filter(filters: dict) -> Filter | None:
    """Build Qdrant filter object from API filter dictionary.

    Converts user-provided filter parameters into Qdrant's Filter format
    for querying the vector database. Currently supports multi-category filtering.

    Args:
        filters: Dictionary of filter parameters. Supported keys:
            - "categories": List of category names to filter by (e.g., ["tipsheet", "audio"]).
                           Empty list or None means no filtering.

    Returns:
        Filter object with conditions if filters are provided, None otherwise.
        Returns None if no valid filters are present.

    Example:
        >>> build_qdrant_filter({"categories": ["tipsheet", "audio"]})
        Filter(must=[FieldCondition(key="metadata.category", match=MatchAny(...))])

        >>> build_qdrant_filter({"categories": []})
        None
    """
    if not filters:
        return None

    conditions: list[FieldCondition] = []

    # Categories filter - nested in metadata (always a list from frontend)
    if filters.get("categories"):
        categories = filters["categories"]
        # Use MatchAny for list values, MatchValue for single values
        if isinstance(categories, list):
            conditions.append(FieldCondition(key="metadata.category", match=MatchAny(any=categories)))
        else:
            conditions.append(FieldCondition(key="metadata.category", match=MatchValue(value=categories)))

    # Cast to the broader condition list type expected by Qdrant Filter.must
    return Filter(must=cast(list[FieldCondition], conditions)) if conditions else None
