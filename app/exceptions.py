"""Custom exception classes for standardized API error handling.

This module provides a hierarchy of custom exceptions that map to specific
HTTP status codes and error codes, ensuring consistent error responses
across all API endpoints.
"""

from typing import Any


class APIError(Exception):
    """Base exception for all API errors.

    All custom exceptions should inherit from this class.
    Provides consistent error structure with status code, error code,
    and optional details for debugging.
    """

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"
    default_message: str = "An internal error occurred"

    def __init__(
        self,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize the API error.

        Args:
            message: Human-readable error message (client-facing)
            details: Additional context for logging (not exposed to clients)
        """
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response (client-facing only)."""
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
        }


class ValidationError(APIError):
    """Raised when request validation fails.

    Use for custom validation errors beyond Pydantic's built-in validation.
    Examples: invalid query parameters, malformed IDs, business rule violations.
    """

    status_code = 400
    error_code = "VALIDATION_ERROR"
    default_message = "Invalid request parameters"


class ResourceNotFoundError(APIError):
    """Raised when a requested resource does not exist.

    Use when a specific resource (by ID) cannot be found in the database.
    """

    status_code = 404
    error_code = "NOT_FOUND"
    default_message = "Resource not found"

    def __init__(
        self,
        resource_type: str = "Resource",
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize resource not found error.

        Args:
            resource_type: Type of resource (e.g., "Resource", "Document")
            resource_id: ID of the missing resource
            details: Additional context for logging
        """
        message = f"{resource_type} not found"
        if resource_id:
            message = f"{resource_type} not found: {resource_id}"
        super().__init__(message=message, details=details)
        self.resource_type = resource_type
        self.resource_id = resource_id


class SearchError(APIError):
    """Raised when a search operation fails.

    Use for errors during semantic search, embedding generation,
    or result processing that are not service availability issues.
    """

    status_code = 500
    error_code = "SEARCH_ERROR"
    default_message = "Search operation failed"


class DatabaseError(APIError):
    """Raised when database operations fail.

    Use for Qdrant connection issues, query failures, or timeouts.
    Returns 503 to indicate temporary service unavailability.
    """

    status_code = 503
    error_code = "DATABASE_ERROR"
    default_message = "Database service temporarily unavailable"


class ModelError(APIError):
    """Raised when ML model operations fail.

    Use for embedding model failures, cross-encoder errors,
    or model loading issues.
    Returns 503 to indicate temporary service unavailability.
    """

    status_code = 503
    error_code = "MODEL_ERROR"
    default_message = "Model service temporarily unavailable"


class RateLimitError(APIError):
    """Raised when rate limit is exceeded.

    Note: This is primarily handled by slowapi's RateLimitExceeded,
    but this class is provided for consistency and custom rate limiting.
    """

    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"
    default_message = "Too many requests. Please try again later."

    def __init__(
        self,
        message: str | None = None,
        retry_after: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        """Initialize rate limit error.

        Args:
            message: Human-readable error message
            retry_after: Seconds until the client can retry
            details: Additional context for logging
        """
        super().__init__(message=message, details=details)
        self.retry_after = retry_after
