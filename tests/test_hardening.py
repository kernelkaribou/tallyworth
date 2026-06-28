"""Tests for security headers, the CSP nonce, and the secret-key guard."""
from __future__ import annotations

import pytest

from app import create_app
from app.config import Config, TestConfig


def test_security_headers_present(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]


def test_csp_nonce_is_applied_to_inline_scripts(client):
    resp = client.get("/")
    csp = resp.headers["Content-Security-Policy"]
    # The nonce in the CSP header must also appear on the inline scripts.
    marker = "'nonce-"
    nonce = csp.split(marker, 1)[1].split("'", 1)[0]
    assert nonce
    assert f'nonce="{nonce}"'.encode() in resp.data


def test_insecure_secret_key_hard_fails_outside_testing():
    class InsecureConfig(Config):
        TESTING = False
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SECRET_KEY = Config.INSECURE_SECRET_KEY

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app(InsecureConfig)


def test_strong_secret_key_starts_outside_testing():
    class SecureConfig(TestConfig):
        TESTING = False
        SECRET_KEY = "a-strong-secret-value"

    app = create_app(SecureConfig)
    assert app is not None
