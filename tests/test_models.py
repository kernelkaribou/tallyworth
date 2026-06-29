"""Tests for seeding and model behaviour."""
from __future__ import annotations

from app.extensions import db
from app.models import Account, AccountType, AccountValue, Classification
from app.seed import BUILTIN_ACCOUNT_TYPES, seed_account_types


def test_seed_creates_all_builtins(app):
    with app.app_context():
        assert AccountType.query.count() == len(BUILTIN_ACCOUNT_TYPES)
        assert AccountType.query.filter_by(name="Property (Equity)").first().tracks_loan
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


def test_seed_migrates_renamed_and_retired_builtins(app):
    with app.app_context():
        # Simulate a database seeded by an older revision.
        AccountType.query.delete()
        db.session.add_all(
            [
                AccountType(
                    name="Real Estate",
                    classification=Classification.asset,
                    tracks_loan=True,
                    is_builtin=True,
                ),
                AccountType(
                    name="CD",
                    classification=Classification.asset,
                    tracks_loan=False,
                    is_builtin=True,
                ),
            ]
        )
        db.session.commit()

        seed_account_types()

        names = {t.name for t in AccountType.query.all()}
        assert "Property (Equity)" in names  # Real Estate renamed in place
        assert "Real Estate" not in names
        assert "CD" not in names  # retired and unused -> removed
        prop = AccountType.query.filter_by(name="Property (Equity)").one()
        assert prop.tracks_loan is True


def test_retired_builtin_still_in_use_is_kept(app):
    with app.app_context():
        mortgage = AccountType(
            name="Mortgage",
            classification=Classification.liability,
            tracks_loan=False,
            is_builtin=True,
        )
        db.session.add(mortgage)
        db.session.flush()
        account = Account(name="Home Loan", account_type=mortgage)
        account.values.append(AccountValue(value_cents=100000))
        db.session.add(account)
        db.session.commit()

        seed_account_types()

        assert AccountType.query.filter_by(name="Mortgage").first() is not None


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
