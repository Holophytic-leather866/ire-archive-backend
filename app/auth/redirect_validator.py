import logging
import re
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Adjust character classes if your app uses other URL characters
ALLOWED_PATH_PATTERN = re.compile(r"^/[a-zA-Z0-9/_.\-]*(\?[a-zA-Z0-9=&%_.\-+:~,]*)?$")

DANGEROUS_PATTERNS = [
    "//",
    "\\",
    "..",
    "%2f%2f",
    "%5c",
    "%00",
    "javascript:",
    "data:",
    "vbscript:",
]


def validate_return_url(url: str | None, default: str = "/") -> str:
    """
    Validate and sanitize a returnTo URL.

    Returns the URL if valid, otherwise returns default.
    Logs rejected URLs at WARNING level for monitoring.
    """
    if not url:
        return default

    # Double-encoding check
    if "%2f" in url.lower() or "%5c" in url.lower():
        logger.warning(f"Rejected returnTo (double-encoded): {url[:100]}")
        return default

    # Must be relative path
    if not url.startswith("/") or url.startswith("//"):
        logger.warning(f"Rejected returnTo (not relative): {url[:100]}")
        return default

    # Dangerous patterns
    lower_url = url.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in lower_url:
            logger.warning(f"Rejected returnTo (dangerous pattern): {url[:100]}")
            return default

    # URL parse check
    try:
        parsed = urlparse(url)
        if parsed.scheme or parsed.netloc:
            logger.warning(f"Rejected returnTo (has scheme/netloc): {url[:100]}")
            return default
    except Exception:
        logger.warning(f"Rejected returnTo (parse error): {url[:100]}")
        return default

    # Userinfo check
    if "@" in url:
        logger.warning(f"Rejected returnTo (contains @): {url[:100]}")
        return default

    # Allowlist pattern
    if not ALLOWED_PATH_PATTERN.match(url):
        logger.warning(f"Rejected returnTo (failed allowlist): {url[:100]}")
        return default

    return url
