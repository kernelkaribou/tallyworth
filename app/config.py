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

    # Single-currency display symbol for alpha.
    CURRENCY_SYMBOL = os.environ.get("CURRENCY_SYMBOL", "$")


class TestConfig(Config):
    """Configuration used by the test suite."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
