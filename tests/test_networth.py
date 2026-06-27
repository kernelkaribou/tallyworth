"""Tests for the net worth service."""
from __future__ import annotations

from app.extensions import db
from app.models import Account, AccountType, AccountValue
from app.services.networth import current_net_worth


def _account(name, type_name, *value_cents):
    account_type = AccountType.query.filter_by(name=type_name).first()
    account = Account(name=name, account_type=account_type)
    db.session.add(account)
    for c in value_cents:
        account.values.append(AccountValue(value_cents=c))
    return account


def test_net_worth_assets_minus_liabilities(app):
    with app.app_context():
        _account("Checking", "Checking", 100000, 150000)  # latest 1500
        _account("Brokerage", "Brokerage / Stocks", 250000)  # 2500
        _account("Visa", "Credit Card", 40000)  # -400
        db.session.commit()

        summary = current_net_worth()
        assert summary.assets_cents == 400000
        assert summary.liabilities_cents == 40000
        assert summary.net_cents == 360000


def test_archived_accounts_excluded(app):
    with app.app_context():
        _account("Checking", "Checking", 100000)
        archived = _account("Old", "Savings", 500000)
        archived.archived = True
        db.session.commit()

        summary = current_net_worth()
        assert summary.assets_cents == 100000
        assert summary.net_cents == 100000


def test_empty_accounts_yield_zero(app):
    with app.app_context():
        summary = current_net_worth()
        assert summary.net_cents == 0
