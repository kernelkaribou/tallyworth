"""Application configuration."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TALLYWORTH_DATA_DIR", BASE_DIR / "data"))


class Config:
    """Base configuration driven by environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-change-me")

    DATA_DIR = DATA_DIR
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{DATA_DIR / 'tallyworth.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sentinel for the known-insecure development secret.
    INSECURE_SECRET_KEY = "dev-insecure-change-me"

    # Display currency. Set DEFAULT_CURRENCY to an ISO code from the catalog
    # (e.g. USD, EUR, GBP, JPY) and the matching symbol is shown in the UI.
    # CURRENCY_SYMBOL is an optional raw override for a symbol not in the
    # catalog; when set it takes precedence over DEFAULT_CURRENCY.
    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "USD")
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL")


class TestConfig(Config):
    """Configuration used by the test suite."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
