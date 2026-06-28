"""Route-level tests for editing and deleting account value snapshots."""
from __future__ import annotations

from app.extensions import db
from app.models import Account, AccountType


def _type_id(name):
    return AccountType.query.filter_by(name=name).first().id


def _make_account(client, app, name, type_name="Checking", initial="100"):
    with app.app_context():
        tid = _type_id(type_name)
    client.post(
        "/accounts",
        data={"name": name, "account_type_id": tid, "initial_value": initial},
        follow_redirects=True,
    )
    with app.app_context():
        account = Account.query.filter_by(name=name).first()
        return account.id, account.values[0].id


def test_edit_value_updates_snapshot(app, client):
    aid, vid = _make_account(client, app, "EditMe", initial="100")
    resp = client.post(
        f"/accounts/{aid}/values/{vid}/edit",
        data={"value": "175.50"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        account = db.session.get(Account, aid)
        assert account.current_value_cents == 17550
        assert len(account.values) == 1


def test_edit_value_get_renders_form(app, client):
    aid, vid = _make_account(client, app, "FormMe", initial="100")
    resp = client.get(f"/accounts/{aid}/values/{vid}/edit")
    assert resp.status_code == 200
    assert b"100.00" in resp.data


def test_edit_value_rejects_bad_money(app, client):
    aid, vid = _make_account(client, app, "BadMoney", initial="100")
    resp = client.post(
        f"/accounts/{aid}/values/{vid}/edit",
        data={"value": "xyz"},
    )
    assert resp.status_code == 400
    with app.app_context():
        assert db.session.get(Account, aid).current_value_cents == 10000


def test_delete_value_removes_snapshot(app, client):
    aid, vid = _make_account(client, app, "DeleteMe", initial="100")
    client.post(f"/accounts/{aid}/values", data={"value": "250"}, follow_redirects=True)
    with app.app_context():
        account = db.session.get(Account, aid)
        assert len(account.values) == 2
    resp = client.post(
        f"/accounts/{aid}/values/{vid}/delete", follow_redirects=True
    )
    assert resp.status_code == 200
    with app.app_context():
        account = db.session.get(Account, aid)
        assert len(account.values) == 1
        assert account.current_value_cents == 25000


def test_edit_value_cross_account_404(app, client):
    aid1, vid1 = _make_account(client, app, "AcctA", initial="100")
    aid2, _ = _make_account(client, app, "AcctB", initial="200")
    resp = client.post(
        f"/accounts/{aid2}/values/{vid1}/edit", data={"value": "5"}
    )
    assert resp.status_code == 404


def test_edit_loan_tracking_value(app, client):
    with app.app_context():
        tid = _type_id("Real Estate")
    client.post(
        "/accounts",
        data={
            "name": "House",
            "account_type_id": tid,
            "initial_value": "300000",
            "initial_loan": "200000",
        },
        follow_redirects=True,
    )
    with app.app_context():
        account = Account.query.filter_by(name="House").first()
        aid, vid = account.id, account.values[0].id
    resp = client.post(
        f"/accounts/{aid}/values/{vid}/edit",
        data={"value": "320000", "loan": "180000"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        account = db.session.get(Account, aid)
        assert account.current_value_cents == 32000000
        assert account.current_loan_cents == 18000000


def test_delete_only_snapshot_renders_empty(app, client):
    aid, vid = _make_account(client, app, "OnlyOne", initial="100")
    client.post(f"/accounts/{aid}/values/{vid}/delete", follow_redirects=True)
    with app.app_context():
        account = db.session.get(Account, aid)
        assert len(account.values) == 0
        assert account.current_value_cents is None
    assert client.get(f"/accounts/{aid}").status_code == 200
    assert client.get("/").status_code == 200


def test_edit_liability_rejects_negative(app, client):
    with app.app_context():
        tid = _type_id("Credit Card")
    client.post(
        "/accounts",
        data={"name": "CC", "account_type_id": tid, "initial_value": "500"},
        follow_redirects=True,
    )
    with app.app_context():
        account = Account.query.filter_by(name="CC").first()
        aid, vid = account.id, account.values[0].id
    resp = client.post(
        f"/accounts/{aid}/values/{vid}/edit", data={"value": "-50"}
    )
    assert resp.status_code == 400
    with app.app_context():
        assert db.session.get(Account, aid).current_value_cents == 50000


def test_edit_loan_tracking_rejects_negative_loan(app, client):
    with app.app_context():
        tid = _type_id("Real Estate")
    client.post(
        "/accounts",
        data={
            "name": "Cabin",
            "account_type_id": tid,
            "initial_value": "100000",
            "initial_loan": "50000",
        },
        follow_redirects=True,
    )
    with app.app_context():
        account = Account.query.filter_by(name="Cabin").first()
        aid, vid = account.id, account.values[0].id
    resp = client.post(
        f"/accounts/{aid}/values/{vid}/edit",
        data={"value": "120000", "loan": "-1"},
    )
    assert resp.status_code == 400
    with app.app_context():
        account = db.session.get(Account, aid)
        assert account.current_value_cents == 10000000
        assert account.current_loan_cents == 5000000
