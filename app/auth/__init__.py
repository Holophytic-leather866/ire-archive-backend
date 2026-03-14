"""MemberSuite SSO authentication module.

This module provides:
- MemberSuite API client for Reverse SSO flow
- Session management with Redis backend
- FastAPI dependencies for protected routes
"""

from app.auth.config import AuthSettings, get_auth_settings
from app.auth.exceptions import (
    AuthenticationError,
    MembershipRequiredError,
    MemberSuiteError,
    SessionExpiredError,
)
from app.auth.session import Session, SessionManager

__all__ = [
    "AuthSettings",
    "get_auth_settings",
    "AuthenticationError",
    "MembershipRequiredError",
    "MemberSuiteError",
    "SessionExpiredError",
    "Session",
    "SessionManager",
]
