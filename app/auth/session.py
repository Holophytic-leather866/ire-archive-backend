"""Redis-backed session management.

Sessions store:
- Encrypted MemberSuite AuthToken (never sent to browser)
- User profile information
- Session metadata (created_at, expires_at)

The browser only receives an opaque session_id via HttpOnly cookie.
"""

import json
import secrets
import time
from dataclasses import dataclass

import structlog
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from redis.asyncio import Redis

from app.auth.config import AuthSettings
from app.auth.exceptions import SessionExpiredError
from app.auth.membersuite_client import MemberSuiteUser

logger = structlog.get_logger()


@dataclass
class Session:
    """Active user session."""

    session_id: str
    user_id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    is_active_member: bool
    membership_id: str | None
    created_at: float
    expires_at: float

    # AuthToken stored but never exposed
    _auth_token: str = ""

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def remaining_seconds(self) -> int:
        return max(0, int(self.expires_at - time.time()))

    def to_dict(self) -> dict:
        """Serialize for Redis storage."""
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "is_active_member": self.is_active_member,
            "membership_id": self.membership_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "auth_token": self._auth_token,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Session":
        """Deserialize from Redis storage."""
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            email=data["email"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            full_name=data["full_name"],
            is_active_member=data["is_active_member"],
            membership_id=data.get("membership_id"),
            created_at=data["created_at"],
            expires_at=data["expires_at"],
            _auth_token=data.get("auth_token", ""),
        )

    def to_public_dict(self) -> dict:
        """User-safe session info (no auth_token)."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "is_active_member": self.is_active_member,
            "session_expires_in": self.remaining_seconds,
        }


class SessionManager:
    """Manages user sessions in Redis."""

    def __init__(self, redis_client: Redis, settings: AuthSettings):
        self.redis = redis_client
        self.settings = settings
        self.serializer = URLSafeTimedSerializer(settings.session_secret)
        self.key_prefix = "session:"

    def _session_key(self, session_id: str) -> str:
        """Redis key for session."""
        return f"{self.key_prefix}{session_id}"

    def _sign_session_id(self, session_id: str) -> str:
        """Sign session ID for cookie (prevents tampering)."""
        return self.serializer.dumps(session_id)

    def _verify_session_id(self, signed_value: str) -> str | None:
        """Verify and extract session ID from signed cookie."""
        try:
            return self.serializer.loads(
                signed_value,
                max_age=self.settings.session_ttl_seconds,
            )
        except (BadSignature, SignatureExpired):
            return None

    async def create_session(self, auth_token: str, user: MemberSuiteUser) -> tuple[Session, str]:
        """Create new session after successful authentication.

        Args:
            auth_token: MemberSuite AuthToken (stored encrypted)
            user: User info from /whoami

        Returns:
            Tuple of (Session, signed_cookie_value)
        """
        session_id = secrets.token_urlsafe(32)
        now = time.time()

        session = Session(
            session_id=session_id,
            user_id=user.user_id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=user.full_name,
            is_active_member=user.is_active_member,
            membership_id=user.membership_id,
            created_at=now,
            expires_at=now + self.settings.session_ttl_seconds,
            _auth_token=auth_token,
        )

        # Store in Redis with TTL
        await self.redis.setex(
            self._session_key(session_id),
            self.settings.session_ttl_seconds,
            json.dumps(session.to_dict()),
        )

        # Sign session ID for cookie
        signed_cookie = self._sign_session_id(session_id)

        logger.info(
            "session_created",
            session_id_prefix=session_id[:8],
            user_id=user.user_id,
            ttl=self.settings.session_ttl_seconds,
        )

        return session, signed_cookie

    async def get_session(self, signed_cookie: str) -> Session | None:
        """Retrieve session from signed cookie value.

        Args:
            signed_cookie: Value from session cookie

        Returns:
            Session if valid, None if invalid/expired
        """
        # Verify signature
        session_id = self._verify_session_id(signed_cookie)
        if not session_id:
            logger.debug("session_signature_invalid")
            return None

        # Fetch from Redis
        data = await self.redis.get(self._session_key(session_id))
        if not data:
            logger.debug("session_not_found", session_id_prefix=session_id[:8])
            return None

        session = Session.from_dict(json.loads(data))

        # Double-check expiry (Redis TTL should handle this, but be safe)
        if session.is_expired:
            await self.delete_session(session_id)
            return None

        return session

    async def extend_session(self, session_id: str) -> bool:
        """Extend session TTL (sliding expiration).

        Call on each authenticated request to keep active sessions alive.

        Returns:
            True if session was extended, False if not found
        """
        key = self._session_key(session_id)
        data = await self.redis.get(key)

        if not data:
            return False

        session_data = json.loads(data)
        session_data["expires_at"] = time.time() + self.settings.session_ttl_seconds

        await self.redis.setex(
            key,
            self.settings.session_ttl_seconds,
            json.dumps(session_data),
        )

        return True

    async def delete_session(self, session_id: str) -> None:
        """Delete session (logout)."""
        await self.redis.delete(self._session_key(session_id))
        logger.info("session_deleted", session_id_prefix=session_id[:8])

    async def get_session_or_raise(self, signed_cookie: str | None) -> Session:
        """Get session or raise SessionExpiredError.

        Use in protected route dependencies.
        """
        if not signed_cookie:
            raise SessionExpiredError()

        session = await self.get_session(signed_cookie)
        if not session:
            raise SessionExpiredError()

        return session
