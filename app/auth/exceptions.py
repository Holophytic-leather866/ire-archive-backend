"""Authentication exceptions with HTTP status code mapping."""


class MemberSuiteError(Exception):
    """Base exception for MemberSuite integration errors."""

    status_code: int = 502  # Bad Gateway (upstream error)
    error_code: str = "MEMBERSUITE_ERROR"

    def __init__(self, message: str, details: dict | None = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(MemberSuiteError):
    """Invalid or expired authentication."""

    status_code = 401
    error_code = "AUTHENTICATION_FAILED"


class SessionExpiredError(AuthenticationError):
    """Session has expired, re-authentication required."""

    error_code = "SESSION_EXPIRED"

    def __init__(self):
        super().__init__("Session expired. Please log in again.")


class MembershipRequiredError(MemberSuiteError):
    """User authenticated but lacks active membership."""

    status_code = 403
    error_code = "MEMBERSHIP_REQUIRED"

    def __init__(self):
        super().__init__("Active IRE membership required. Visit ire.org/join to become a member.")


class TokenExchangeError(MemberSuiteError):
    """Failed to exchange tokenGUID for AuthToken."""

    error_code = "TOKEN_EXCHANGE_FAILED"

    def __init__(self, status_code: int):
        super().__init__(
            f"Failed to exchange authentication token (status: {status_code})",
            {"upstream_status": status_code},
        )


class ConfigurationError(MemberSuiteError):
    """Authentication not properly configured."""

    status_code = 503  # Service Unavailable
    error_code = "AUTH_NOT_CONFIGURED"

    def __init__(self, missing: list[str]):
        super().__init__(
            "Authentication service not configured",
            {"missing_config": missing},
        )
