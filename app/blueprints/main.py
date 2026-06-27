"""Main blueprint: landing page and health check."""
from __future__ import annotations

from flask import Blueprint, render_template

from app.models.account import Account
from app.services.networth import current_net_worth

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Render the dashboard with the current net worth and account list."""
    active_accounts = (
        Account.query.filter_by(archived=False).order_by(Account.name).all()
    )
    summary = current_net_worth(active_accounts)
    return render_template(
        "index.html",
        summary=summary,
        accounts=active_accounts,
        active_count=len(active_accounts),
    )


@bp.get("/healthz")
def healthz():
    """Lightweight health check for container orchestration."""
    return {"status": "ok"}, 200
