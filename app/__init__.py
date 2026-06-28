"""Application factory for Tallyworth."""
from __future__ import annotations

from pathlib import Path

from flask import Flask

from .config import Config
from .extensions import csrf, db, migrate


def create_app(config_object: type[Config] | Config = Config) -> Flask:
    """Create and configure a Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    _ensure_data_dir(app)
    _check_secret_key(app)

    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    from . import models  # noqa: F401  (register models with SQLAlchemy/Alembic)
    from .seed import register_seed_cli, seed_account_types  # noqa: F401

    register_seed_cli(app)

    from .blueprints.main import bp as main_bp
    from .blueprints.accounts import bp as accounts_bp
    from .blueprints.cashflow import bp as cashflow_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(accounts_bp)
    app.register_blueprint(cashflow_bp)

    _register_currency(app)

    return app


def _register_currency(app: Flask) -> None:
    """Expose the currency symbol and a money formatter to all templates.

    The symbol comes from CURRENCY_SYMBOL when set (a raw override), otherwise
    from the DEFAULT_CURRENCY ISO code resolved against the known catalog.
    """
    from app.currencies import get_currency

    override = app.config.get("CURRENCY_SYMBOL")
    if override:
        symbol = override
    else:
        symbol = get_currency(app.config.get("DEFAULT_CURRENCY")).symbol

    @app.template_filter("money")
    def _money(cents: int | None) -> str:
        if cents is None:
            return "-"
        sign = "-" if cents < 0 else ""
        return f"{sign}{symbol}{abs(cents) / 100:,.2f}"

    @app.context_processor
    def _inject_currency() -> dict:
        return {"currency_symbol": symbol}


def _ensure_data_dir(app: Flask) -> None:
    """Create the data directory only for an on-disk SQLite database."""
    uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
    if uri.startswith("sqlite:///") and ":memory:" not in uri:
        data_dir = app.config.get("DATA_DIR")
        if data_dir:
            Path(data_dir).mkdir(parents=True, exist_ok=True)


def _check_secret_key(app: Flask) -> None:
    """Warn loudly when running on an unset or insecure default secret key.

    To be tightened to a hard failure once sessions/auth land (see
    copilot-instructions.md).
    """
    if app.config.get("TESTING"):
        return
    insecure = app.config.get("INSECURE_SECRET_KEY", "dev-insecure-change-me")
    if app.config.get("SECRET_KEY") in (None, "", insecure):
        app.logger.warning(
            "SECRET_KEY is unset or using the insecure default. "
            "Set a strong SECRET_KEY before enabling sessions or authentication."
        )
