"""Tests for seeding and model behaviour."""
from __future__ import annotations

from app.extensions import db
from app.models import Account, AccountType, AccountValue, Classification
from app.seed import BUILTIN_ACCOUNT_TYPES, seed_account_types


def test_seed_creates_all_builtins(app):
    with app.app_context():
        assert AccountType.query.count() == len(BUILTIN_ACCOUNT_TYPES)
        assert AccountType.query.filter_by(name="Real Estate").first().tracks_loan
        assert (
            AccountType.query.filter_by(name="Credit Card").first().classification
            == Classification.liability
        )


def test_seed_is_idempotent(app):
    with app.app_context():
        before = AccountType.query.count()
        added = seed_account_types()
        assert added == 0
        assert AccountType.query.count() == before


def test_latest_value_tracks_running_value(app):
    with app.app_context():
        checking = AccountType.query.filter_by(name="Checking").first()
        account = Account(name="Test", account_type=checking)
        db.session.add(account)
        account.values.append(AccountValue(value_cents=10000))
        account.values.append(AccountValue(value_cents=5000))
        account.values.append(AccountValue(value_cents=15000))
        db.session.commit()
        assert account.current_value_cents == 15000
        assert account.signed_value_cents == 15000


def test_liability_signed_value_is_negative(app):
    with app.app_context():
        card = AccountType.query.filter_by(name="Credit Card").first()
        account = Account(name="Visa", account_type=card)
        db.session.add(account)
        account.values.append(AccountValue(value_cents=30000))
        db.session.commit()
        assert account.signed_value_cents == -30000


def test_account_without_value_contributes_zero(app):
    with app.app_context():
        checking = AccountType.query.filter_by(name="Checking").first()
        account = Account(name="Empty", account_type=checking)
        db.session.add(account)
        db.session.commit()
        assert account.current_value_cents is None
        assert account.signed_value_cents == 0
