"""Tests for ADDITIONAL_ALLOWED_ORIGINS configuration parsing."""

import importlib
import json

import pytest


def reload_config(monkeypatch, env_value: str | None):
    """Reload app.config with the given ADDITIONAL_ALLOWED_ORIGINS value.

    Returns the reloaded config module so callers can inspect ALLOWED_ORIGINS.
    """
    import app.config as config_module

    if env_value is None:
        monkeypatch.delenv("ADDITIONAL_ALLOWED_ORIGINS", raising=False)
    else:
        monkeypatch.setenv("ADDITIONAL_ALLOWED_ORIGINS", env_value)

    # Force a full re-evaluation of the module-level code.
    importlib.reload(config_module)
    return config_module


def test_default_origins_present(monkeypatch):
    """Built-in localhost and production origins are always present."""
    cfg = reload_config(monkeypatch, None)
    assert "http://localhost:5173" in cfg.ALLOWED_ORIGINS
    assert "http://localhost:4173" in cfg.ALLOWED_ORIGINS
    assert "https://archive.ire.org" in cfg.ALLOWED_ORIGINS


def test_additional_origins_json_array(monkeypatch):
    """JSON array format appends extra origins."""
    extra = ["https://custom.example.com", "https://staging.example.com"]
    cfg = reload_config(monkeypatch, json.dumps(extra))
    for origin in extra:
        assert origin in cfg.ALLOWED_ORIGINS


def test_additional_origins_comma_separated(monkeypatch):
    """Comma-separated fallback format appends extra origins."""
    cfg = reload_config(monkeypatch, "https://a.example.com, https://b.example.com")
    assert "https://a.example.com" in cfg.ALLOWED_ORIGINS
    assert "https://b.example.com" in cfg.ALLOWED_ORIGINS


def test_additional_origins_no_duplicates(monkeypatch):
    """Existing origins in ADDITIONAL_ALLOWED_ORIGINS are not duplicated."""
    cfg = reload_config(monkeypatch, '["https://archive.ire.org"]')
    assert cfg.ALLOWED_ORIGINS.count("https://archive.ire.org") == 1


def test_additional_origins_empty_string(monkeypatch):
    """Empty string leaves default origins unchanged."""
    cfg = reload_config(monkeypatch, "")
    assert cfg.ALLOWED_ORIGINS == [
        "http://localhost:5173",
        "http://localhost:4173",
        "https://archive.ire.org",
    ]


def test_additional_origins_invalid_json_falls_back_to_csv(monkeypatch):
    """Malformed JSON falls back to comma-separated parsing."""
    cfg = reload_config(monkeypatch, "https://fallback.example.com")
    assert "https://fallback.example.com" in cfg.ALLOWED_ORIGINS


def test_additional_origins_json_non_array_raises(monkeypatch):
    """JSON value that is not an array raises ValueError during module load."""
    with pytest.raises(ValueError):
        reload_config(monkeypatch, '{"url": "https://bad.example.com"}')
