"""Authentication configuration with validation.

Environment variables:
- MS_TENANT_ID: MemberSuite tenant/partition key (required)
- MS_ASSOCIATION_ID: Association GUID (required)
- MS_API_BASE_URL: MemberSuite API base (default: https://rest.membersuite.com)
- REDIS_URL: Redis connection string (required for sessions)
- FRONTEND_URL: Frontend origin for redirects (required)
- SESSION_SECRET: Secret for session signing (required, min 32 chars)
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AuthSettings:
    """Immutable authentication settings."""

    # MemberSuite configuration
    tenant_id: str
    association_id: str
    api_base_url: str = "https://rest.membersuite.com"

    # Session configuration
    redis_url: str = ""
    session_ttl_seconds: int = 3600  # 1 hour (matches AuthToken)
    session_cookie_name: str = "ire_session"

    # URLs
    frontend_url: str = "https://archive.ire.org"
    callback_path: str = "/auth/callback"

    # Security
    session_secret: str = ""
    require_active_membership: bool = True

    @property
    def callback_url(self) -> str:
        """Full callback URL for MemberSuite redirect.

        Uses localhost in development (when FRONTEND_URL contains 'localhost')
        to enable local testing without tunnel services. MemberSuite doesn't
        whitelist domains, so localhost callbacks work fine.
        """
        if "localhost" in self.frontend_url:
            return f"http://localhost:8000{self.callback_path}"
        return f"https://api.archive.ire.org{self.callback_path}"

    @property
    def api_url(self) -> str:
        """Derive API URL from frontend URL."""
        # archive.ire.org → api.archive.ire.org
        if "localhost" in self.frontend_url:
            return "http://localhost:8000"
        return self.frontend_url.replace("://", "://api.")

    def validate(self) -> list[str]:
        """Return list of missing required configuration."""
        missing = []
        if not self.tenant_id:
            missing.append("MS_TENANT_ID")
        if not self.association_id:
            missing.append("MS_ASSOCIATION_ID")
        if not self.redis_url:
            missing.append("REDIS_URL")
        if not self.session_secret or len(self.session_secret) < 32:
            missing.append("SESSION_SECRET (min 32 characters)")
        return missing

    @property
    def is_configured(self) -> bool:
        """Check if auth is fully configured."""
        return len(self.validate()) == 0


@lru_cache
def get_auth_settings() -> AuthSettings:
    """Get cached auth settings from environment."""
    return AuthSettings(
        tenant_id=os.getenv("MS_TENANT_ID", ""),
        association_id=os.getenv("MS_ASSOCIATION_ID", ""),
        api_base_url=os.getenv("MS_API_BASE_URL", "https://rest.membersuite.com"),
        redis_url=os.getenv("REDIS_URL", ""),
        session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "86400")),
        session_cookie_name=os.getenv("SESSION_COOKIE_NAME", "ire_session"),
        frontend_url=os.getenv("FRONTEND_URL", "https://archive.ire.org"),
        session_secret=os.getenv("SESSION_SECRET", ""),
        require_active_membership=os.getenv("MS_REQUIRE_MEMBERSHIP", "true").lower() == "true",
    )
