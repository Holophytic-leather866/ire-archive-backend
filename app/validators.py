"""Input validation utilities for API requests."""

from typing import Literal, Optional

from app.config import MAX_OFFSET, MAX_QUERY_LENGTH, VALID_CATEGORIES

# Type alias for sort options
SortOrder = Literal["relevance", "newest", "oldest"]


def validate_categories(categories: list[str] | None) -> list[str] | None:
    """Validate list of categories against allowed values.

    Args:
        categories: List of category strings to validate

    Returns:
        Validated categories list or None (if empty or None)

    Raises:
        ValueError: If any category is invalid
    """
    if categories is None or len(categories) == 0:
        return None

    # Handle 'all' as special "no filter" value
    if categories == ["all"]:
        return None

    invalid = [c for c in categories if c not in VALID_CATEGORIES]
    if invalid:
        valid_list = ", ".join(sorted(VALID_CATEGORIES))
        raise ValueError(f"Invalid categories: {invalid}. Valid categories: {valid_list}")
    return categories


def sanitize_query(query: str | None) -> str | None:
    """Sanitize and validate query string.

    Args:
        query: Query string from request

    Returns:
        Sanitized query or None (empty strings return None)
    """
    if query is None:
        return None

    # Strip whitespace
    query = query.strip()

    # Return None for empty strings (model validator will check if category is present)
    if not query:
        return None

    return query
