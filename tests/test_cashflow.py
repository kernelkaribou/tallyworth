"""Tests for the cashflow service and routes."""
from __future__ import annotations

from app.extensions import db
from app.models import CashflowEntry, CashflowKind
from app.services.cashflow import cashflow_summary


def _entry(kind, name, cents):
    db.session.add(CashflowEntry(kind=kind, name=name, amount_cents=cents))


def test_summary_empty_is_zero_and_green(app):
    with app.app_context():
        summary = cashflow_summary()
        assert summary.income_cents == 0
        assert summary.expense_cents == 0
        assert summary.net_cents == 0
        assert summary.in_green is True
        assert summary.has_entries is False


def test_summary_has_entries_when_present(app):
    with app.app_context():
        _entry(CashflowKind.income, "Salary", 1000)
        db.session.commit()
        assert cashflow_summary().has_entries is True


def test_negative_amount_rejected_by_db_constraint(app):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with app.app_context():
        db.session.add(
            CashflowEntry(kind=CashflowKind.expense, name="Bad", amount_cents=-1)
        )
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_dashboard_empty_cashflow_shows_setup(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Not set up" in resp.data


def test_summary_totals_and_sign(app):
    with app.app_context():
        _entry(CashflowKind.income, "Salary", 300000)
        _entry(CashflowKind.income, "Side gig", 50000)
        _entry(CashflowKind.expense, "Rent", 150000)
        _entry(CashflowKind.expense, "Utilities", 20000)
        db.session.commit()

        summary = cashflow_summary()
        assert summary.income_cents == 350000
        assert summary.expense_cents == 170000
        assert summary.net_cents == 180000
        assert summary.in_green is True


def test_summary_in_the_red(app):
    with app.app_context():
        _entry(CashflowKind.income, "Salary", 100000)
        _entry(CashflowKind.expense, "Rent", 150000)
        db.session.commit()

        summary = cashflow_summary()
        assert summary.net_cents == -50000
        assert summary.in_green is False


def test_create_income_and_expense(client, app):
    client.post(
        "/cashflow",
        data={"kind": "income", "name": "Salary", "amount": "1000"},
        follow_redirects=True,
    )
    client.post(
        "/cashflow",
        data={"kind": "expense", "name": "Rent", "amount": "$400.50"},
        follow_redirects=True,
    )
    with app.app_context():
        summary = cashflow_summary()
        assert summary.income_cents == 100000
        assert summary.expense_cents == 40050


def test_create_rejects_negative_amount(client, app):
    resp = client.post(
        "/cashflow",
        data={"kind": "expense", "name": "Bad", "amount": "-50"},
        follow_redirects=True,
    )
    assert b"valid, non-negative amount" in resp.data
    with app.app_context():
        assert CashflowEntry.query.count() == 0


def test_create_rejects_bad_kind(client, app):
    client.post(
        "/cashflow",
        data={"kind": "bogus", "name": "X", "amount": "10"},
        follow_redirects=True,
    )
    with app.app_context():
        assert CashflowEntry.query.count() == 0


def test_update_and_delete(client, app):
    client.post(
        "/cashflow",
        data={"kind": "expense", "name": "Rent", "amount": "400"},
        follow_redirects=True,
    )
    with app.app_context():
        entry_id = CashflowEntry.query.one().id

    client.post(
        f"/cashflow/{entry_id}/edit",
        data={"name": "Rent + parking", "amount": "450"},
        follow_redirects=True,
    )
    with app.app_context():
        entry = db.session.get(CashflowEntry, entry_id)
        assert entry.name == "Rent + parking"
        assert entry.amount_cents == 45000

    client.post(f"/cashflow/{entry_id}/delete", follow_redirects=True)
    with app.app_context():
        assert CashflowEntry.query.count() == 0


def test_dashboard_shows_cashflow(client, app):
    client.post(
        "/cashflow",
        data={"kind": "income", "name": "Salary", "amount": "1000"},
        follow_redirects=True,
    )
    client.post(
        "/cashflow",
        data={"kind": "expense", "name": "Rent", "amount": "400"},
        follow_redirects=True,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data
    assert b"Monthly cashflow" in body
    # Expanded Income - Expenses = Cashflow equation
    assert b"Income" in body
    assert b"Expenses" in body
    assert b">Cashflow<" in body
