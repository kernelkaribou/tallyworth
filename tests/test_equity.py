"""Tests for the asset equity (loan-tracking) workflow."""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Account, AccountType, AccountValue
from app.services.networth import (
    current_net_worth,
    display_value_map,
    latest_snapshot_map,
    net_worth_series,
)


def _loan_account(name="House", type_name="Property (Equity)"):
    account_type = AccountType.query.filter_by(name=type_name).first()
    account = Account(name=name, account_type=account_type)
    db.session.add(account)
    return account


def test_equity_is_value_minus_loan(app):
    with app.app_context():
        house = _loan_account()
        house.values.append(AccountValue(value_cents=30000000, loan_cents=18000000))
        db.session.commit()

        assert house.current_value_cents == 30000000
        assert house.current_loan_cents == 18000000
        assert house.equity_cents == 12000000
        assert house.signed_value_cents == 12000000


def test_equity_can_be_negative_when_underwater(app):
    with app.app_context():
        car = _loan_account(name="Car", type_name="Vehicle (Equity)")
        car.values.append(AccountValue(value_cents=1500000, loan_cents=2000000))
        db.session.commit()
        assert car.equity_cents == -500000
        assert car.signed_value_cents == -500000


def test_net_worth_grosses_up_loan_accounts(app):
    with app.app_context():
        house = _loan_account()
        house.values.append(AccountValue(value_cents=30000000, loan_cents=18000000))

        checking_type = AccountType.query.filter_by(name="Checking").first()
        checking = Account(name="Checking", account_type=checking_type)
        db.session.add(checking)
        checking.values.append(AccountValue(value_cents=500000))
        db.session.commit()

        summary = current_net_worth()
        # Gross: full market value (30,000,000) + checking (500,000) in assets,
        # loan (18,000,000) in liabilities; net is unchanged equity + checking.
        assert summary.assets_cents == 30500000
        assert summary.liabilities_cents == 18000000
        assert summary.net_cents == 12500000


def test_net_worth_underwater_loan_account(app):
    with app.app_context():
        car = _loan_account(name="Car", type_name="Vehicle (Equity)")
        car.values.append(AccountValue(value_cents=1500000, loan_cents=2000000))
        db.session.commit()

        summary = current_net_worth()
        # Underwater: market value is an asset, the larger loan a liability, so
        # net worth goes negative without any negative asset figure.
        assert summary.assets_cents == 1500000
        assert summary.liabilities_cents == 2000000
        assert summary.net_cents == -500000


def test_display_value_map_shows_market_value(app):
    with app.app_context():
        house = _loan_account()
        house.values.append(AccountValue(value_cents=30000000, loan_cents=18000000))
        db.session.commit()

        snapshots = latest_snapshot_map([house.id])
        assert snapshots[house.id] == (30000000, 18000000)
        values = display_value_map([house], snapshots)
        assert values[house.id] == 30000000


def test_series_forward_fills_equity(app):
    with app.app_context():
        house = _loan_account()
        house.values.append(
            AccountValue(
                value_cents=30000000,
                loan_cents=20000000,
                recorded_at=datetime(2026, 1, 1),
            )
        )
        # Loan paid down later -> equity rises even though value is flat
        house.values.append(
            AccountValue(
                value_cents=30000000,
                loan_cents=15000000,
                recorded_at=datetime(2026, 6, 1),
            )
        )
        db.session.commit()

        points = net_worth_series()
        assert [p.net_cents for p in points] == [10000000, 15000000]
        assert points[-1].net_cents == current_net_worth().net_cents


def test_negative_loan_rejected_by_db_constraint(app):
    with app.app_context():
        house = _loan_account()
        house.values.append(AccountValue(value_cents=100000, loan_cents=-1))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_create_loan_account_with_initial_value_and_loan(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Property (Equity)").first().id
    client.post(
        "/accounts",
        data={
            "name": "Lake House",
            "account_type_id": type_id,
            "initial_value": "300000",
            "initial_loan": "180000",
        },
        follow_redirects=True,
    )
    with app.app_context():
        account = Account.query.filter_by(name="Lake House").one()
        assert account.current_value_cents == 30000000
        assert account.current_loan_cents == 18000000
        assert account.equity_cents == 12000000


def test_loan_account_requires_loan_when_recording_value(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Vehicle (Equity)").first().id
    client.post(
        "/accounts",
        data={"name": "Truck", "account_type_id": type_id},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Truck").one().id

    resp = client.post(
        f"/accounts/{account_id}/values",
        data={"value": "25000"},  # no loan provided
        follow_redirects=True,
    )
    assert b"loan balance is required" in resp.data.lower()
    with app.app_context():
        assert db.session.get(Account, account_id).current_value_cents is None


def test_detail_chart_label_is_equity_for_loan_account(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Vehicle (Equity)").first().id
    client.post(
        "/accounts",
        data={
            "name": "Van",
            "account_type_id": type_id,
            "initial_value": "20000",
            "initial_loan": "5000",
        },
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Van").one().id
    resp = client.get(f"/accounts/{account_id}")
    assert resp.status_code == 200
    assert b'data-label="Equity"' in resp.data
    assert b"Loan balance" in resp.data


def test_loan_without_market_value_is_rejected(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Property (Equity)").first().id
    resp = client.post(
        "/accounts",
        data={
            "name": "Cabin",
            "account_type_id": type_id,
            "initial_loan": "50000",  # loan but no value
        },
        follow_redirects=True,
    )
    assert b"market value" in resp.data.lower()
    with app.app_context():
        assert Account.query.filter_by(name="Cabin").first() is None


def test_negative_market_value_rejected_for_loan_account(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Vehicle (Equity)").first().id
    client.post(
        "/accounts",
        data={
            "name": "Scooter",
            "account_type_id": type_id,
            "initial_value": "1000",
            "initial_loan": "0",
        },
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Scooter").one().id
    resp = client.post(
        f"/accounts/{account_id}/values",
        data={"value": "-500", "loan": "0"},
        follow_redirects=True,
    )
    assert b"market value cannot be negative" in resp.data.lower()


def test_loan_input_prefilled_with_latest_balance(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Property (Equity)").first().id
    client.post(
        "/accounts",
        data={
            "name": "Townhouse",
            "account_type_id": type_id,
            "initial_value": "250000",
            "initial_loan": "120000",
        },
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Townhouse").one().id
    resp = client.get(f"/accounts/{account_id}")
    assert b'value="120000.00"' in resp.data


def test_dashboard_shows_market_value_only_for_loan_account(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Property (Equity)").first().id
    client.post(
        "/accounts",
        data={
            "name": "Bungalow",
            "account_type_id": type_id,
            "initial_value": "400000",
            "initial_loan": "300000",
        },
        follow_redirects=True,
    )
    body = client.get("/").get_data(as_text=True)
    # High-level tile shows the current market value, not the loan/equity math.
    assert "400,000.00" in body
    assert "300,000.00 loan" not in body
    assert "100,000.00 equity" not in body


def test_accounts_list_shows_market_value_only_for_loan_account(client, app):
    with app.app_context():
        type_id = AccountType.query.filter_by(name="Property (Equity)").first().id
    client.post(
        "/accounts",
        data={
            "name": "Bungalow",
            "account_type_id": type_id,
            "initial_value": "400000",
            "initial_loan": "300000",
        },
        follow_redirects=True,
    )
    body = client.get("/accounts").get_data(as_text=True)
    assert "400,000.00" in body  # full market value as the current value
    assert "300,000.00 loan" not in body
    assert "100,000.00 equity" not in body
