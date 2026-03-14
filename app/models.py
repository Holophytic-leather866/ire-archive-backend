"""Pydantic models for API requests and responses."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import DEFAULT_LIMIT, MAX_LIMIT, MAX_OFFSET, MAX_QUERY_LENGTH, MIN_LIMIT
from app.validators import SortOrder, sanitize_query, validate_categories

# Search mode type
SearchMode = Literal["hybrid", "keyword"]


class SearchQuery(BaseModel):
    """Search query parameters with validation."""

    query: str | None = Field(default=None, max_length=MAX_QUERY_LENGTH, description="Search query text")
    limit: int = Field(
        default=DEFAULT_LIMIT, ge=MIN_LIMIT, le=MAX_LIMIT, description=f"Results per page ({MIN_LIMIT}-{MAX_LIMIT})"
    )
    offset: int = Field(default=0, ge=0, le=MAX_OFFSET, description=f"Number of results to skip (max {MAX_OFFSET:,})")
    categories: list[str] | None = Field(default=None, description="Filter by categories (list of category names)")
    sort_by: SortOrder = Field(default="relevance", description="Sort order: relevance, newest, or oldest")
    search_mode: SearchMode = Field(
        default="hybrid",
        description="Search mode: 'hybrid' (semantic + keyword) or 'keyword' (traditional keyword search only)",
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str | None) -> str | None:
        """Sanitize and validate query string."""
        return sanitize_query(v)

    @field_validator("categories")
    @classmethod
    def validate_categories_value(cls, v: list[str] | None) -> list[str] | None:
        """Validate categories against allowed values."""
        return validate_categories(v)

    @model_validator(mode="after")
    def require_query_or_categories(self) -> "SearchQuery":
        """Ensure either query or categories filter is provided."""
        if not self.query and not self.categories:
            raise ValueError("Either 'query' or 'categories' must be provided for search")
        return self


class SearchResponse(BaseModel):
    """Search response model."""

    query: str
    results: list
    count: int
    total: int  # Total matching documents
    limit: int  # Results per page
    offset: int  # Current offset
    has_more: bool  # Whether there are more results


class SimilarResource(BaseModel):
    """Similar resource model."""

    vector_id: str = Field(description="Vector ID (MD5 hash) for API lookups")
    resource_id: str = Field(description="Original IRE resource ID")
    title: str
    score: float
    metadata: dict


class SimilarResourcesResponse(BaseModel):
    """Response model for similar resources endpoint."""

    vector_id: str = Field(description="Vector ID of the source resource")
    similar_resources: list[SimilarResource]
    count: int


class ErrorResponse(BaseModel):
    """Standardized error response model.

    All API errors return this consistent format for predictable client handling.
    """

    error: str = Field(description="Error code (e.g., VALIDATION_ERROR, NOT_FOUND)")
    message: str = Field(description="Human-readable error message")
    status_code: int = Field(description="HTTP status code")
    request_id: str | None = Field(default=None, description="Request ID for tracking/support")
