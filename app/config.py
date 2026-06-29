"""Application configuration."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("TALLYWORTH_DATA_DIR", BASE_DIR / "data"))


class Config:
    """Base configuration driven by environment variables."""

    # A strong key is generated and persisted in DATA_DIR on first start (see
    # app/__init__.py:_ensure_secret_key), so a fresh deploy needs nothing more
    # than a mounted data volume.
    SECRET_KEY = None

    DATA_DIR = DATA_DIR
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / 'tallyworth.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Display currency. Set DEFAULT_CURRENCY to an ISO code from the catalog
    # (e.g. USD, EUR, GBP, JPY) and the matching symbol is shown in the UI.
    # CURRENCY_SYMBOL is an optional raw override for a symbol not in the
    # catalog; when set it takes precedence over DEFAULT_CURRENCY.
    DEFAULT_CURRENCY = os.environ.get("DEFAULT_CURRENCY", "USD")
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL")

    # Display timezone. Timestamps are always stored in UTC; this only controls
    # the zone snapshot dates are shown in. Set TZ to any IANA name (e.g.
    # America/New_York); an unknown value falls back to UTC.
    DISPLAY_TIMEZONE = os.environ.get("TZ", "UTC")


class TestConfig(Config):
    """Configuration used by the test suite."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
