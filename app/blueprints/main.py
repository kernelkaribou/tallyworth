"""Main blueprint: landing page and health check."""
from __future__ import annotations

from datetime import timezone

from flask import Blueprint, render_template
from sqlalchemy.orm import selectinload

from app.models.account import Account
from app.services.cashflow import cashflow_summary
from app.services.networth import (
    account_trends,
    current_net_worth,
    display_value_map,
    latest_snapshot_map,
    loan_balance_map,
    net_worth_series,
)

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
    snapshots = latest_snapshot_map([a.id for a in active_accounts])
    values = display_value_map(active_accounts, snapshots)
    loans = loan_balance_map(active_accounts, snapshots)
    trends = account_trends(active_accounts)
    summary = current_net_worth(active_accounts, snapshots)
    series = net_worth_series(active_accounts)
    chart_points = [
        {
            "x": int(p.recorded_at.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "y": p.net_cents / 100,
        }
        for p in series
    ]
    return render_template(
        "index.html",
        summary=summary,
        accounts=active_accounts,
        values=values,
        loans=loans,
        trends=trends,
        active_count=len(active_accounts),
        chart_points=chart_points,
        cashflow=cashflow_summary(),
    )


@bp.get("/healthz")
def healthz():
    """Lightweight health check for container orchestration."""
    return {"status": "ok"}, 200
