"""Tests for security headers, the CSP nonce, and secret-key provisioning."""
from __future__ import annotations

from app import create_app
from app.config import Config


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


def test_secret_key_is_autoprovisioned_and_persisted(tmp_path):
    class DiskConfig(Config):
        TESTING = False
        DATA_DIR = tmp_path
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SECRET_KEY = None

    app = create_app(DiskConfig)
    key_file = tmp_path / "secret_key"
    assert key_file.exists()
    assert app.config["SECRET_KEY"] == key_file.read_text().strip()
    assert len(app.config["SECRET_KEY"]) >= 32

    # A second start reuses the persisted key instead of generating a new one.
    app2 = create_app(DiskConfig)
    assert app2.config["SECRET_KEY"] == app.config["SECRET_KEY"]


def test_explicit_secret_key_overrides_autoprovision(tmp_path):
    class SecureConfig(Config):
        TESTING = False
        DATA_DIR = tmp_path
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SECRET_KEY = "a-strong-secret-value"

    app = create_app(SecureConfig)
    assert app.config["SECRET_KEY"] == "a-strong-secret-value"
    assert not (tmp_path / "secret_key").exists()
