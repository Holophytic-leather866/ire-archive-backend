"""Rate limiting configuration and utilities.

Provides rate limiting for API endpoints with support for:
- Per-client rate limits based on IP address
- Optional bypass tokens for internal testing
- IP whitelist for monitoring tools
- Standard rate limit headers (X-RateLimit-*)
- Structured 429 error responses

Bypass Mechanism:
    slowapi's `exempt_when` parameter is called WITHOUT arguments, so we cannot
    use a function that requires the request object. Instead, we use middleware
    to check bypass conditions BEFORE rate limiting and set a flag on request.state.
    A custom `limit_with_bypass` decorator checks this flag and skips the rate
    limiter entirely for bypass requests.
"""

import asyncio
from collections.abc import Callable
from functools import wraps
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import (
    RATE_LIMIT_BYPASS_TOKEN,
    RATE_LIMIT_HEADERS_ENABLED,
    RATE_LIMIT_REDIS_URL,
    RATE_LIMIT_STORAGE,
    RATE_LIMIT_WHITELIST,
)


def check_bypass_conditions(request: Request) -> bool:
    """Check if request should bypass rate limiting.

    Args:
        request: FastAPI request object

    Returns:
        True if request should skip rate limiting
    """
    # Check for bypass token header (internal use only)
    bypass_token = request.headers.get("X-RateLimit-Bypass")
    if bypass_token and RATE_LIMIT_BYPASS_TOKEN and bypass_token == RATE_LIMIT_BYPASS_TOKEN:
        return True

    # Extract client IP for whitelist check
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = get_remote_address(request)

    # Check IP whitelist
    if client_ip in RATE_LIMIT_WHITELIST:
        return True

    return False


class RateLimitBypassMiddleware(BaseHTTPMiddleware):
    """Middleware to check bypass conditions before rate limiting.

    Sets a flag on request.state that limit_with_bypass checks
    to skip rate limiting for exempt requests.
    """

    async def dispatch(self, request: Request, call_next):
        """Check bypass conditions and set flag on request state."""
        # Check if this request should bypass rate limiting
        request.state.rate_limit_bypass = check_bypass_conditions(request)
        return await call_next(request)


def get_client_identifier(request: Request) -> str:
    """Extract client identifier for rate limiting.

    Uses X-Forwarded-For header for reverse proxies (like Fly.io),
    falls back to direct connection IP.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address string
    """
    # Extract client IP
    # Check for forwarded header (common with reverse proxies like Fly.io)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Take the first IP (original client)
        client_ip = forwarded.split(",")[0].strip()
    else:
        # Fall back to direct connection IP
        client_ip = get_remote_address(request)

    return client_ip


def create_limiter() -> Limiter:
    """Create and configure the rate limiter.

    Returns:
        Configured Limiter instance with appropriate storage backend
    """
    # Choose storage backend
    storage_uri = None
    if RATE_LIMIT_STORAGE == "redis" and RATE_LIMIT_REDIS_URL:
        storage_uri = RATE_LIMIT_REDIS_URL

    limiter = Limiter(
        key_func=get_client_identifier,
        storage_uri=storage_uri,
        headers_enabled=RATE_LIMIT_HEADERS_ENABLED,
    )

    return limiter


# Global limiter instance
limiter = create_limiter()


def limit_with_bypass(limit_string: str) -> Callable:
    """Rate limit decorator with bypass support.

    Checks request.state.rate_limit_bypass (set by RateLimitBypassMiddleware).
    If True, skips rate limiting entirely. Otherwise applies normal limit.

    Args:
        limit_string: Rate limit string (e.g., "60/minute;10/second")

    Returns:
        Decorator function that applies rate limiting with bypass support
    """

    def decorator(func: Callable) -> Callable:
        # Apply the slowapi limiter to create the rate-limited version
        limited_func = limiter.limit(limit_string)(func)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Find request in kwargs or args
            request = kwargs.get("request")
            if request is None:
                # Request should be the first positional arg after self/cls
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            # Check bypass flag set by middleware
            if request and getattr(request.state, "rate_limit_bypass", False):
                # Bypass rate limiting - call original function directly
                return await func(*args, **kwargs)

            # Apply rate limiting
            return await limited_func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Find request in kwargs or args
            request = kwargs.get("request")
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            # Check bypass flag set by middleware
            if request and getattr(request.state, "rate_limit_bypass", False):
                # Bypass rate limiting - call original function directly
                return func(*args, **kwargs)

            # Apply rate limiting
            return limited_func(*args, **kwargs)

        # Return appropriate wrapper based on whether func is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Handle rate limit exceeded errors.

    Returns a structured JSON response with retry information and proper headers.

    Args:
        request: FastAPI request that triggered the rate limit
        exc: RateLimitExceeded exception with retry information

    Returns:
        JSONResponse with 429 status and retry information
    """
    # Extract retry-after from the exception (default to 60 seconds)
    retry_after = int(getattr(exc, "retry_after", 60))

    # Get request ID if available (from middleware)
    request_id = getattr(request.state, "request_id", None)

    return JSONResponse(
        status_code=429,
        content={
            "error": "RATE_LIMIT_EXCEEDED",
            "message": f"Too many requests. Please retry after {retry_after} seconds.",
            "retry_after": retry_after,
            "request_id": request_id,
        },
        headers={
            "Retry-After": str(retry_after),
        },
    )
