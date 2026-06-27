"""Cashflow blueprint: light monthly income and expense tracking."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models.cashflow import CashflowEntry, CashflowKind
from app.money import MoneyError, parse_money_to_cents
from app.services.cashflow import cashflow_summary

bp = Blueprint("cashflow", __name__)


@bp.get("/cashflow")
def list_cashflow():
    income = (
        CashflowEntry.query.filter_by(kind=CashflowKind.income)
        .order_by(CashflowEntry.name)
        .all()
    )
    expenses = (
        CashflowEntry.query.filter_by(kind=CashflowKind.expense)
        .order_by(CashflowEntry.name)
        .all()
    )
    return render_template(
        "cashflow/list.html",
        income=income,
        expenses=expenses,
        summary=cashflow_summary(),
    )


@bp.post("/cashflow")
def create_cashflow():
    kind = _parse_kind(request.form.get("kind"))
    name = (request.form.get("name") or "").strip()
    amount = _parse_amount(request.form.get("amount"))

    if kind is None:
        flash("Please choose income or expense.", "error")
    elif not name:
        flash("A name is required.", "error")
    elif amount is None:
        flash("Enter a valid, non-negative amount.", "error")
    else:
        db.session.add(CashflowEntry(kind=kind, name=name, amount_cents=amount))
        db.session.commit()
        flash(f"{kind.value.capitalize()} '{name}' added.", "success")
    return redirect(url_for("cashflow.list_cashflow"))


@bp.post("/cashflow/<int:entry_id>/edit")
def update_cashflow(entry_id: int):
    entry = db.get_or_404(CashflowEntry, entry_id)
    name = (request.form.get("name") or "").strip()
    amount = _parse_amount(request.form.get("amount"))

    if not name:
        flash("A name is required.", "error")
    elif amount is None:
        flash("Enter a valid, non-negative amount.", "error")
    else:
        entry.name = name
        entry.amount_cents = amount
        db.session.commit()
        flash("Entry updated.", "success")
    return redirect(url_for("cashflow.list_cashflow"))


@bp.post("/cashflow/<int:entry_id>/delete")
def delete_cashflow(entry_id: int):
    entry = db.get_or_404(CashflowEntry, entry_id)
    db.session.delete(entry)
    db.session.commit()
    flash("Entry removed.", "success")
    return redirect(url_for("cashflow.list_cashflow"))


def _parse_kind(raw: str | None) -> CashflowKind | None:
    try:
        return CashflowKind(raw)
    except ValueError:
        return None


def _parse_amount(raw: str | None) -> int | None:
    """Parse a money string to non-negative cents, or None if invalid."""
    if raw is None or raw.strip() == "":
        return None
    try:
        cents = parse_money_to_cents(raw)
    except MoneyError:
        return None
    if cents < 0:
        return None
    return cents
