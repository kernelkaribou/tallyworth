"""Application factory for Tallyworth."""
from __future__ import annotations

import secrets
from pathlib import Path

from flask import Flask, g

from .config import Config
from .extensions import csrf, db, migrate


def create_app(config_object: type[Config] | Config = Config) -> Flask:
    """Create and configure a Flask application instance."""
    app = Flask(__name__)
    app.config.from_object(config_object)

    _ensure_data_dir(app)
    _ensure_secret_key(app)

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
    _register_datetime(app)
    _register_security_headers(app)

    return app


def _register_datetime(app: Flask) -> None:
    """Render stored UTC timestamps in the configured display timezone.

    Snapshot timestamps are stored as naive UTC. We resolve the TZ env var to an
    IANA zone (falling back to UTC when unknown) and expose a ``localdt`` filter
    plus the zone name to templates, so dates read in the operator's local time
    while storage stays UTC. The JS charts receive the same zone name to keep the
    axis and tooltips consistent with the tables.
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    name = (app.config.get("DISPLAY_TIMEZONE") or "UTC").strip() or "UTC"
    try:
        zone = ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        zone, name = timezone.utc, "UTC"

    @app.template_filter("localdt")
    def _localdt(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M %Z") -> str:
        if value is None:
            return "-"
        aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
        return aware.astimezone(zone).strftime(fmt)

    @app.context_processor
    def _inject_timezone() -> dict:
        return {"display_timezone": name}


def _register_security_headers(app: Flask) -> None:
    """Attach defence-in-depth response headers, including a CSP.

    A per-request nonce is generated for the handful of inline <script> blocks
    (the pre-paint theme bootstrap, the theme toggle, and the account form's
    loan-field reveal) so the Content-Security-Policy can forbid arbitrary
    inline script while still allowing those trusted snippets.
    """

    @app.before_request
    def _set_csp_nonce() -> None:
        g.csp_nonce = secrets.token_urlsafe(16)

    @app.context_processor
    def _inject_csp_nonce() -> dict:
        return {"csp_nonce": getattr(g, "csp_nonce", "")}

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        nonce = getattr(g, "csp_nonce", "")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "base-uri 'none'; "
            "frame-ancestors 'none'; "
            "object-src 'none'",
        )
        return response


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


def _ensure_secret_key(app: Flask) -> None:
    """Auto-provision a persistent secret key next to the database.

    Tallyworth has no user accounts and is a single self-hosted instance; the
    secret only signs session cookies and CSRF tokens for this one process.
    Rather than make operators generate and manage a key, we persist a strong
    random one in DATA_DIR so it survives restarts while keeping deployment to
    "mount a data volume."
    """
    if app.config.get("TESTING"):
        app.config["SECRET_KEY"] = "testing-only-secret"
        return

    data_dir = Path(app.config["DATA_DIR"])
    data_dir.mkdir(parents=True, exist_ok=True)
    key_file = data_dir / "secret_key"
    key = key_file.read_text().strip() if key_file.exists() else ""
    if len(key) < 32:
        key = secrets.token_urlsafe(48)
        key_file.write_text(key)
        key_file.chmod(0o600)
    app.config["SECRET_KEY"] = key
