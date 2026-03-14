"""Authentication API routes.

Handles:
- GET /auth/login - Get MemberSuite login redirect URL
- GET /auth/callback - Handle MemberSuite callback, create session
- GET /auth/me - Get current user info
- POST /auth/logout - End session
- GET /auth/status - Auth service health check
"""

from typing import Optional
from urllib.parse import quote

import structlog
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel

from app.auth.config import AuthSettings, get_auth_settings
from app.auth.dependencies import get_optional_session, require_session
from app.auth.exceptions import ConfigurationError
from app.auth.membersuite_client import MemberSuiteClient
from app.auth.redirect_validator import validate_return_url
from app.auth.session import Session, SessionManager
from app.dependencies import get_membersuite_client, get_session_manager

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["authentication"])

# Return URL cookie configuration
RETURN_TO_COOKIE_NAME = "ire_return_to"
RETURN_TO_COOKIE_MAX_AGE = 600  # 10 minutes


# === Response Models ===
class LoginResponse(BaseModel):
    """Response from /auth/login."""

    redirect_url: str


class UserResponse(BaseModel):
    """Current user information."""

    user_id: str
    email: str
    first_name: str
    last_name: str
    full_name: str
    is_active_member: bool
    session_expires_in: int


class AuthStatusResponse(BaseModel):
    """Auth service status."""

    configured: bool
    frontend_url: str
    callback_url: str


class LogoutResponse(BaseModel):
    """Logout confirmation."""

    success: bool
    message: str


# === Return URL Helpers ===
def _get_return_to_serializer(settings: AuthSettings) -> URLSafeTimedSerializer:
    """Get serializer for signing returnTo cookie."""
    return URLSafeTimedSerializer(settings.session_secret, salt="return_to")


def _sign_return_to(return_to: str, settings: AuthSettings) -> str:
    """Sign returnTo value for cookie."""
    return _get_return_to_serializer(settings).dumps(return_to)


def _verify_return_to(signed_value: str, settings: AuthSettings) -> str | None:
    """Verify and extract returnTo from signed cookie. Returns None if invalid."""
    try:
        return _get_return_to_serializer(settings).loads(
            signed_value,
            max_age=RETURN_TO_COOKIE_MAX_AGE,
        )
    except (BadSignature, SignatureExpired):
        return None


def _is_dev_environment(settings: AuthSettings) -> bool:
    """Check if running in development (localhost)."""
    frontend = settings.frontend_url.lower()
    return "localhost" in frontend or "127.0.0.1" in frontend


# === Routes ===
@router.get("/status", response_model=AuthStatusResponse)
async def auth_status():
    """Check if authentication is configured."""
    settings = get_auth_settings()
    return AuthStatusResponse(
        configured=settings.is_configured,
        frontend_url=settings.frontend_url,
        callback_url=settings.callback_url if settings.is_configured else "",
    )


@router.get("/login", response_model=LoginResponse)
async def get_login_url(
    response: Response,
    returnTo: str = Query(default="/", alias="returnTo", description="Post-login redirect"),
    client: MemberSuiteClient = Depends(get_membersuite_client),
):
    """Get MemberSuite login URL. Stores returnTo in signed cookie."""
    settings = get_auth_settings()
    if not settings.is_configured:
        raise ConfigurationError(settings.validate())

    # Validate returnTo to prevent open redirect
    safe_return_to = validate_return_url(returnTo, default="/")

    logger.info("login_initiated", return_to=safe_return_to[:50])

    # Store in signed cookie that survives MemberSuite redirect
    is_dev = _is_dev_environment(settings)
    response.set_cookie(
        key=RETURN_TO_COOKIE_NAME,
        value=_sign_return_to(safe_return_to, settings),
        httponly=True,
        secure=not is_dev,  # False for localhost HTTP, True for production HTTPS
        samesite="lax" if is_dev else "none",  # lax for same-origin dev, none for cross-origin prod
        max_age=RETURN_TO_COOKIE_MAX_AGE,
        path="/",
        domain=".archive.ire.org" if not is_dev else None,  # Share across subdomains in prod
    )

    redirect_url = await client.get_login_redirect_url()
    return LoginResponse(redirect_url=redirect_url)


@router.get("/callback")
async def handle_callback(
    request: Request,
    response: Response,
    tokenGUID: str = Query(..., description="Token from MemberSuite"),
    client: MemberSuiteClient = Depends(get_membersuite_client),
    session_mgr: SessionManager = Depends(get_session_manager),
):
    """Handle MemberSuite callback. Reads returnTo from cookie, creates session."""
    settings = get_auth_settings()
    is_dev = _is_dev_environment(settings)

    logger.info("auth_callback_received", token_guid_prefix=tokenGUID[:8])

    # Read and verify returnTo cookie
    return_to = "/"
    return_to_cookie = request.cookies.get(RETURN_TO_COOKIE_NAME)
    if return_to_cookie:
        verified = _verify_return_to(return_to_cookie, settings)
        if verified:
            return_to = verified
            logger.info("return_to_restored", return_to=return_to[:50])
        else:
            logger.warning("return_to_cookie_invalid_or_expired")

    # Authenticate with MemberSuite
    try:
        auth_token, user = await client.authenticate_and_verify(
            tokenGUID,
            require_membership=settings.require_active_membership,
        )
    except Exception as e:
        logger.error("auth_callback_failed", error=str(e))
        # Redirect with error, preserve returnTo for retry
        error_response = RedirectResponse(
            url=f"{settings.frontend_url}/login?error=auth_failed&returnTo={quote(return_to)}",
            status_code=302,
        )
        error_response.delete_cookie(key=RETURN_TO_COOKIE_NAME, path="/")
        return error_response

    # Create session
    session, signed_cookie = await session_mgr.create_session(auth_token, user)

    logger.info("auth_callback_success", user_id=user.user_id, return_to=return_to[:50])

    # Redirect to frontend with returnTo parameter
    redirect_response = RedirectResponse(
        url=f"{settings.frontend_url}/login?returnTo={quote(return_to)}",
        status_code=302,
    )

    # Set session cookie
    redirect_response.set_cookie(
        key=settings.session_cookie_name,
        value=signed_cookie,
        httponly=True,
        secure=not is_dev,
        samesite="lax" if is_dev else "none",
        max_age=settings.session_ttl_seconds,
        path="/",
        domain=".archive.ire.org" if not is_dev else None,  # Share across subdomains in prod
    )

    # Clear returnTo cookie (one-time use)
    redirect_response.delete_cookie(
        key=RETURN_TO_COOKIE_NAME,
        path="/",
        domain=".archive.ire.org" if not is_dev else None,
    )

    return redirect_response


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    session: Session = Depends(require_session),
):
    """Get current authenticated user's information."""
    return UserResponse(**session.to_public_dict())


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    session: Session | None = Depends(get_optional_session),
    session_mgr: SessionManager = Depends(get_session_manager),
):
    """End the current session.

    Deletes server-side session and clears cookie.
    """
    settings = get_auth_settings()

    if session:
        await session_mgr.delete_session(session.session_id)

    # Clear the session cookie
    is_dev = _is_dev_environment(settings)
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=True,
        httponly=True,
        samesite="none",
        domain=".archive.ire.org" if not is_dev else None,
    )

    # Clear returnTo cookie if present
    response.delete_cookie(
        key=RETURN_TO_COOKIE_NAME,
        path="/",
        domain=".archive.ire.org" if not is_dev else None,
    )

    return LogoutResponse(success=True, message="Logged out successfully")
