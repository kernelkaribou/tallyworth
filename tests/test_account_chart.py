"""Tests for the account history chart on the detail page."""
from __future__ import annotations

from app.models import Account, AccountType


def _make_account(name="Chartable", type_name="Checking"):
    from app.extensions import db

    account_type = AccountType.query.filter_by(name=type_name).first()
    account = Account(name=name, account_type=account_type)
    db.session.add(account)
    db.session.commit()
    return account.id


def test_detail_has_chart_when_history_exists(app, client):
    with app.app_context():
        account_id = _make_account()
    client.post(
        f"/accounts/{account_id}/values", data={"value": "100"}, follow_redirects=True
    )
    client.post(
        f"/accounts/{account_id}/values", data={"value": "150"}, follow_redirects=True
    )
    resp = client.get(f"/accounts/{account_id}")
    assert resp.status_code == 200
    assert b"account-history-chart" in resp.data
    assert b"account-history-data" in resp.data
    assert b"chart.umd.min.js" in resp.data
    # Two data points serialised as {"x": ..., "y": ...}
    assert resp.data.count(b'"x":') == 2
    assert b'"y": 100.0' in resp.data or b'"y":100.0' in resp.data


def test_detail_has_no_chart_without_history(app, client):
    with app.app_context():
        account_id = _make_account(name="Empty")
    resp = client.get(f"/accounts/{account_id}")
    assert resp.status_code == 200
    assert b"account-history-chart" not in resp.data
    assert b"chart.umd.min.js" not in resp.data


def test_dashboard_has_networth_chart_with_history(app, client):
    with app.app_context():
        account_id = _make_account(name="Dash")
    client.post(
        f"/accounts/{account_id}/values", data={"value": "500"}, follow_redirects=True
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"networth-chart" in resp.data
    assert b"networth-data" in resp.data
    assert b"chart.umd.min.js" in resp.data


def test_dashboard_has_no_chart_without_history(app, client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"networth-chart" not in resp.data
    assert b"chart.umd.min.js" not in resp.data

