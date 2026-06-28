"""Tests for per-account dashboard trend tiles."""
from __future__ import annotations

from app.extensions import db
from app.models import Account, AccountType
from app.services.networth import account_trends


def _make_account(name, type_name="Checking"):
    account_type = AccountType.query.filter_by(name=type_name).first()
    account = Account(name=name, account_type=account_type)
    db.session.add(account)
    db.session.commit()
    return account.id


def test_trend_up_for_rising_asset(app):
    with app.app_context():
        aid = _make_account("Rising")
        acct = db.session.get(Account, aid)
        acct.values.append(_value(100_00))
        acct.values.append(_value(150_00))
        db.session.commit()
        trend = account_trends([acct])[aid]
        assert trend.direction == "up"
        assert trend.improved is True
        assert trend.current_cents == 150_00
        assert trend.previous_cents == 100_00
        assert trend.delta_cents == 50_00
        assert trend.spark_points is not None


def test_trend_down_for_falling_asset(app):
    with app.app_context():
        aid = _make_account("Falling")
        acct = db.session.get(Account, aid)
        acct.values.append(_value(200_00))
        acct.values.append(_value(120_00))
        db.session.commit()
        trend = account_trends([acct])[aid]
        assert trend.direction == "down"
        assert trend.improved is False
        assert trend.delta_cents == -80_00


def test_trend_liability_paid_down_is_improvement(app):
    with app.app_context():
        aid = _make_account("Card", type_name="Credit Card")
        acct = db.session.get(Account, aid)
        acct.values.append(_value(500_00))
        acct.values.append(_value(300_00))
        db.session.commit()
        trend = account_trends([acct])[aid]
        # The number fell, but for a liability that is good for net worth.
        assert trend.direction == "down"
        assert trend.improved is True


def test_trend_none_without_two_values(app):
    with app.app_context():
        aid = _make_account("Single")
        acct = db.session.get(Account, aid)
        acct.values.append(_value(100_00))
        db.session.commit()
        trend = account_trends([acct])[aid]
        assert trend.direction == "none"
        assert trend.improved is None
        assert trend.delta_cents is None
        assert trend.spark_points is None
        assert trend.has_history is False


def test_trend_flat_when_value_unchanged(app):
    with app.app_context():
        aid = _make_account("Flat")
        acct = db.session.get(Account, aid)
        acct.values.append(_value(100_00))
        acct.values.append(_value(100_00))
        db.session.commit()
        trend = account_trends([acct])[aid]
        assert trend.direction == "flat"
        assert trend.improved is None
        # A flat sparkline is still drawable (mid-height line).
        assert trend.spark_points is not None


def test_dashboard_renders_tiles_with_sparkline(app, client):
    with app.app_context():
        aid = _make_account("Tiled")
    client.post(f"/accounts/{aid}/values", data={"value": "100"}, follow_redirects=True)
    client.post(f"/accounts/{aid}/values", data={"value": "150"}, follow_redirects=True)
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<polyline" in resp.data  # sparkline present
    assert b"Tiled" in resp.data


def _value(value_cents, loan_cents=None):
    from app.models import AccountValue

    return AccountValue(value_cents=value_cents, loan_cents=loan_cents)
