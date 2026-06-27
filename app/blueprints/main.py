"""Main blueprint: landing page and health check."""
from __future__ import annotations

from flask import Blueprint, render_template

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Render the dashboard landing page."""
    return render_template("index.html")


@bp.get("/healthz")
def healthz():
    """Lightweight health check for container orchestration."""
    return {"status": "ok"}, 200
