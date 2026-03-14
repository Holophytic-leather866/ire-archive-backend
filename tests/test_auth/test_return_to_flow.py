"""Tests for the returnTo signed cookie flow."""

import time
from unittest.mock import patch

import pytest

from app.auth.config import AuthSettings
from app.auth.routes import (
    RETURN_TO_COOKIE_MAX_AGE,
    _is_dev_environment,
    _sign_return_to,
    _verify_return_to,
)


@pytest.fixture
def dev_settings():
    return AuthSettings(
        tenant_id="test",
        association_id="test",
        redis_url="redis://localhost",
        session_secret="x" * 32,
        frontend_url="http://localhost:5173",
    )


@pytest.fixture
def prod_settings():
    return AuthSettings(
        tenant_id="test",
        association_id="test",
        redis_url="redis://localhost",
        session_secret="x" * 32,
        frontend_url="https://app.example.com",
    )


class TestCookieSigning:
    """Test signing and verification of returnTo cookie."""

    def test_roundtrip(self, dev_settings):
        """Signed value verifies correctly."""
        original = "/search?q=test"
        signed = _sign_return_to(original, dev_settings)
        assert _verify_return_to(signed, dev_settings) == original

    def test_tampered_rejected(self, dev_settings):
        """Tampered value is rejected."""
        signed = _sign_return_to("/search", dev_settings)
        tampered = signed[:-5] + "XXXXX"
        assert _verify_return_to(tampered, dev_settings) is None

    def test_wrong_secret_rejected(self, dev_settings):
        """Value signed with different secret is rejected."""
        signed = _sign_return_to("/search", dev_settings)
        other = AuthSettings(
            tenant_id="t",
            association_id="a",
            redis_url="redis://localhost",
            session_secret="y" * 32,
            frontend_url="http://localhost:5173",
        )
        assert _verify_return_to(signed, other) is None

    def test_expired_rejected(self, dev_settings):
        """Expired value is rejected."""
        signed = _sign_return_to("/search", dev_settings)
        future = time.time() + RETURN_TO_COOKIE_MAX_AGE + 100
        with patch("itsdangerous.timed.time.time", return_value=future):
            assert _verify_return_to(signed, dev_settings) is None

    def test_garbage_rejected(self, dev_settings):
        """Random garbage is rejected."""
        assert _verify_return_to("not-valid", dev_settings) is None
        assert _verify_return_to("", dev_settings) is None


class TestEnvironmentDetection:
    """Test dev vs prod environment detection."""

    def test_localhost_is_dev(self, dev_settings):
        assert _is_dev_environment(dev_settings) is True

    def test_127_is_dev(self):
        settings = AuthSettings(
            tenant_id="t",
            association_id="a",
            redis_url="redis://localhost",
            session_secret="x" * 32,
            frontend_url="http://127.0.0.1:5173",
        )
        assert _is_dev_environment(settings) is True

    def test_production_is_not_dev(self, prod_settings):
        assert _is_dev_environment(prod_settings) is False
