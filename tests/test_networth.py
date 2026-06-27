"""Tests for the net worth service."""
from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.models import Account, AccountType, AccountValue
from app.services.networth import current_net_worth, net_worth_series


def _account(name, type_name, *value_cents):
    account_type = AccountType.query.filter_by(name=type_name).first()
    account = Account(name=name, account_type=account_type)
    db.session.add(account)
    for c in value_cents:
        account.values.append(AccountValue(value_cents=c))
    return account


def _at(account, value_cents, recorded_at):
    account.values.append(
        AccountValue(value_cents=value_cents, recorded_at=recorded_at)
    )


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


def test_series_forward_fills_across_accounts(app):
    with app.app_context():
        checking = _account("Checking", "Checking")
        visa = _account("Visa", "Credit Card")
        _at(checking, 100000, datetime(2026, 1, 1))  # +1000
        _at(visa, 40000, datetime(2026, 1, 5))  # -400 (checking carried at 1000)
        _at(checking, 150000, datetime(2026, 1, 10))  # +1500, visa still -400
        db.session.commit()

        points = net_worth_series()
        assert [p.net_cents for p in points] == [100000, 60000, 110000]
        assert [p.recorded_at for p in points] == [
            datetime(2026, 1, 1),
            datetime(2026, 1, 5),
            datetime(2026, 1, 10),
        ]


def test_series_final_point_matches_current(app):
    with app.app_context():
        checking = _account("Checking", "Checking")
        visa = _account("Visa", "Credit Card")
        _at(checking, 100000, datetime(2026, 1, 1))
        _at(visa, 40000, datetime(2026, 1, 5))
        _at(checking, 150000, datetime(2026, 1, 10))
        db.session.commit()

        points = net_worth_series()
        assert points[-1].net_cents == current_net_worth().net_cents


def test_series_collapses_same_timestamp(app):
    with app.app_context():
        checking = _account("Checking", "Checking")
        savings = _account("Savings", "Savings")
        _at(checking, 100000, datetime(2026, 2, 1))
        _at(savings, 50000, datetime(2026, 2, 1))
        db.session.commit()

        points = net_worth_series()
        assert len(points) == 1
        assert points[0].net_cents == 150000


def test_series_excludes_archived(app):
    with app.app_context():
        checking = _account("Checking", "Checking")
        old = _account("Old", "Savings")
        old.archived = True
        _at(checking, 100000, datetime(2026, 3, 1))
        _at(old, 999999, datetime(2026, 3, 2))
        db.session.commit()

        points = net_worth_series()
        assert all(p.net_cents == 100000 for p in points)
        assert len(points) == 1


def test_series_empty_without_values(app):
    with app.app_context():
        _account("Checking", "Checking")
        db.session.commit()
        assert net_worth_series() == []


def test_series_same_account_same_timestamp_breaks_ties_by_id(app):
    with app.app_context():
        checking = _account("Checking", "Checking")
        ts = datetime(2026, 4, 1)
        _at(checking, 100000, ts)
        _at(checking, 250000, ts)  # later insertion (higher id) must win
        db.session.commit()

        points = net_worth_series()
        assert len(points) == 1
        assert points[0].net_cents == 250000
        assert points[-1].net_cents == current_net_worth().net_cents


