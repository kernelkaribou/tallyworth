"""Accounts blueprint: account and account-type CRUD plus value snapshots."""
from __future__ import annotations

from datetime import timezone

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.money import MoneyError, parse_money_to_cents
from app.models.account import Account, AccountValue
from app.models.account_type import AccountType, Classification
from app.services.networth import display_value_map, latest_snapshot_map

bp = Blueprint("accounts", __name__)


def _ordered_types() -> list[AccountType]:
    return AccountType.query.order_by(
        AccountType.classification, AccountType.name
    ).all()


@bp.get("/accounts")
def list_accounts():
    accounts = (
        Account.query.options(selectinload(Account.account_type))
        .order_by(Account.archived, Account.name)
        .all()
    )
    values = display_value_map(accounts)
    return render_template("accounts/list.html", accounts=accounts, values=values)


@bp.get("/accounts/new")
def new_account():
    return render_template(
        "accounts/form.html", account=None, account_types=_ordered_types()
    )


@bp.post("/accounts")
def create_account():
    name = (request.form.get("name") or "").strip()
    type_id = request.form.get("account_type_id", type=int)
    account_type = db.session.get(AccountType, type_id) if type_id else None

    if not name:
        flash("Account name is required.", "error")
    elif account_type is None:
        flash("Please choose an account type.", "error")

    if not name or account_type is None:
        return (
            render_template(
                "accounts/form.html", account=None, account_types=_ordered_types()
            ),
            400,
        )

    account = Account(name=name, account_type=account_type)
    db.session.add(account)
    db.session.flush()

    error = _maybe_add_value(
        account,
        request.form.get("initial_value"),
        request.form.get("initial_loan"),
    )
    if error:
        db.session.rollback()
        flash(error, "error")
        return (
            render_template(
                "accounts/form.html", account=None, account_types=_ordered_types()
            ),
            400,
        )

    db.session.commit()
    flash(f"Account '{account.name}' created.", "success")
    return redirect(url_for("accounts.account_detail", account_id=account.id))


@bp.get("/accounts/<int:account_id>")
def account_detail(account_id: int):
    account = db.get_or_404(Account, account_id)
    ordered = sorted(account.values, key=lambda v: (v.recorded_at, v.id))
    history = list(reversed(ordered))
    chart_points = [
        {
            "x": int(v.recorded_at.replace(tzinfo=timezone.utc).timestamp() * 1000),
            "y": (v.equity_cents if account.tracks_loan else v.value_cents) / 100,
        }
        for v in ordered
    ]
    return render_template(
        "accounts/detail.html",
        account=account,
        history=history,
        chart_points=chart_points,
    )


@bp.get("/accounts/<int:account_id>/edit")
def edit_account(account_id: int):
    account = db.get_or_404(Account, account_id)
    return render_template(
        "accounts/form.html", account=account, account_types=_ordered_types()
    )


@bp.post("/accounts/<int:account_id>/edit")
def update_account(account_id: int):
    account = db.get_or_404(Account, account_id)
    name = (request.form.get("name") or "").strip()
    type_id = request.form.get("account_type_id", type=int)
    account_type = db.session.get(AccountType, type_id) if type_id else None

    if not name or account_type is None:
        flash("Name and account type are required.", "error")
        return (
            render_template(
                "accounts/form.html",
                account=account,
                account_types=_ordered_types(),
            ),
            400,
        )

    account.name = name
    account.account_type = account_type
    db.session.commit()
    flash("Account updated.", "success")
    return redirect(url_for("accounts.account_detail", account_id=account.id))


@bp.post("/accounts/<int:account_id>/values")
def add_value(account_id: int):
    account = db.get_or_404(Account, account_id)
    error = _maybe_add_value(
        account,
        request.form.get("value"),
        request.form.get("loan"),
        required=True,
    )
    if error:
        db.session.rollback()
        flash(error, "error")
    else:
        db.session.commit()
        flash("Value recorded.", "success")
    return redirect(url_for("accounts.account_detail", account_id=account.id))


@bp.post("/accounts/<int:account_id>/archive")
def toggle_archive(account_id: int):
    account = db.get_or_404(Account, account_id)
    account.archived = not account.archived
    db.session.commit()
    state = "archived" if account.archived else "restored"
    flash(f"Account {state}.", "success")
    return redirect(url_for("accounts.list_accounts"))


@bp.get("/account-types")
def list_account_types():
    return render_template(
        "account_types/list.html", account_types=_ordered_types()
    )


@bp.post("/account-types")
def create_account_type():
    name = (request.form.get("name") or "").strip()
    classification_raw = request.form.get("classification") or ""
    tracks_loan = request.form.get("tracks_loan") == "on"

    if not name:
        flash("Type name is required.", "error")
        return redirect(url_for("accounts.list_account_types"))
    if AccountType.query.filter(AccountType.name.ilike(name)).first():
        flash(f"An account type named '{name}' already exists.", "error")
        return redirect(url_for("accounts.list_account_types"))
    try:
        classification = Classification(classification_raw)
    except ValueError:
        flash("Please choose a valid classification.", "error")
        return redirect(url_for("accounts.list_account_types"))

    if tracks_loan and classification == Classification.liability:
        flash(
            "Loan tracking applies to assets only, not liabilities.",
            "error",
        )
        return redirect(url_for("accounts.list_account_types"))

    db.session.add(
        AccountType(
            name=name,
            classification=classification,
            tracks_loan=tracks_loan,
            is_builtin=False,
        )
    )
    db.session.commit()
    flash(f"Account type '{name}' added.", "success")
    return redirect(url_for("accounts.list_account_types"))


def _maybe_add_value(
    account: Account,
    raw_value: str | None,
    raw_loan: str | None = None,
    required: bool = False,
) -> str | None:
    """Add a value snapshot from raw money strings. Returns an error message or None.

    For loan-tracking accounts a non-negative loan balance is required alongside
    the market value (enter 0 if the asset is owned outright).
    """
    if raw_value is None or raw_value.strip() == "":
        if (
            account.account_type.tracks_loan
            and raw_loan is not None
            and raw_loan.strip() != ""
        ):
            return "Enter a market value to go with the loan balance."
        return "A value is required." if required else None
    try:
        cents = parse_money_to_cents(raw_value)
    except MoneyError as exc:
        return str(exc)
    if (
        account.account_type.classification == Classification.liability
        and cents < 0
    ):
        return "Enter the amount owed as a positive number."
    if account.account_type.tracks_loan and cents < 0:
        return "Market value cannot be negative."

    loan_cents: int | None = None
    if account.account_type.tracks_loan:
        if raw_loan is None or raw_loan.strip() == "":
            return "A loan balance is required (enter 0 if owned outright)."
        try:
            loan_cents = parse_money_to_cents(raw_loan)
        except MoneyError as exc:
            return str(exc)
        if loan_cents < 0:
            return "Loan balance cannot be negative."

    account.values.append(AccountValue(value_cents=cents, loan_cents=loan_cents))
    return None
