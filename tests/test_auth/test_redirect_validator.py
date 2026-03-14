import pytest

from app.auth.redirect_validator import validate_return_url


class TestValidateReturnUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "/",
            "/search",
            "/resource/abc-123",
            "/resource/2024.01.15-report",
            "/search?q=test",
            "/search?q=test&page=2",
            "/search?q=climate:energy",
        ],
    )
    def test_valid_urls(self, url):
        assert validate_return_url(url) == url

    @pytest.mark.parametrize(
        "url",
        [
            "https://evil.com",
            "//evil.com",
            "/\\evil.com",
            "/../etc/passwd",
            "javascript:alert(1)",
            "",
            None,
            "//@evil.com",
            "/%2f/evil.com",
        ],
    )
    def test_invalid_urls(self, url):
        assert validate_return_url(url) == "/"

    def test_custom_default(self):
        assert validate_return_url("https://evil.com", default="/home") == "/home"
