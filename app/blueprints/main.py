"""Main blueprint: landing page and health check."""
from __future__ import annotations

from flask import Blueprint, render_template
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.services.networth import current_net_worth, latest_value_cents_map

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Render the dashboard with the current net worth and account list."""
    active_accounts = (
        Account.query.options(selectinload(Account.account_type))
        .filter_by(archived=False)
        .order_by(Account.name)
        .all()
    )
    values = latest_value_cents_map([a.id for a in active_accounts])
    summary = current_net_worth(active_accounts, values)
    return render_template(
        "index.html",
        summary=summary,
        accounts=active_accounts,
        values=values,
        active_count=len(active_accounts),
    )


@bp.get("/healthz")
def healthz():
    """Lightweight health check for container orchestration."""
    return {"status": "ok"}, 200
