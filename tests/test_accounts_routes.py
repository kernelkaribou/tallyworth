"""Route-level tests for accounts CRUD and value snapshots."""
from __future__ import annotations

from app.extensions import db
from app.models import Account, AccountType


def _type_id(name):
    return AccountType.query.filter_by(name=name).first().id


def test_create_account_with_initial_value(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    resp = client.post(
        "/accounts",
        data={"name": "Main", "account_type_id": checking, "initial_value": "1,200.50"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        account = Account.query.filter_by(name="Main").first()
        assert account is not None
        assert account.current_value_cents == 120050


def test_create_account_requires_name(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    resp = client.post(
        "/accounts", data={"name": "", "account_type_id": checking}
    )
    assert resp.status_code == 400
    with app.app_context():
        assert Account.query.count() == 0


def test_create_account_rejects_bad_money(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    resp = client.post(
        "/accounts",
        data={"name": "Bad", "account_type_id": checking, "initial_value": "xyz"},
    )
    assert resp.status_code == 400
    with app.app_context():
        assert Account.query.count() == 0


def test_add_value_updates_running_value(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    client.post(
        "/accounts",
        data={"name": "Run", "account_type_id": checking, "initial_value": "100"},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Run").first().id
    client.post(
        f"/accounts/{account_id}/values", data={"value": "250"}, follow_redirects=True
    )
    with app.app_context():
        account = db.session.get(Account, account_id)
        assert account.current_value_cents == 25000
        assert len(account.values) == 2


def test_archive_toggle(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    client.post(
        "/accounts",
        data={"name": "Arch", "account_type_id": checking},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Arch").first().id
    client.post(f"/accounts/{account_id}/archive", follow_redirects=True)
    with app.app_context():
        assert db.session.get(Account, account_id).archived is True
    client.post(f"/accounts/{account_id}/archive", follow_redirects=True)
    with app.app_context():
        assert db.session.get(Account, account_id).archived is False


def test_create_custom_account_type(app, client):
    resp = client.post(
        "/account-types",
        data={"name": "Pension", "classification": "asset", "tracks_loan": "off"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        t = AccountType.query.filter_by(name="Pension").first()
        assert t is not None and t.is_builtin is False


def test_custom_type_rejects_duplicate(app, client):
    resp = client.post(
        "/account-types",
        data={"name": "Checking", "classification": "asset"},
        follow_redirects=True,
    )
    assert b"already exists" in resp.data


def test_dashboard_shows_net_worth(app, client):
    with app.app_context():
        checking = _type_id("Checking")
        card = _type_id("Credit Card")
    client.post(
        "/accounts",
        data={"name": "Cash", "account_type_id": checking, "initial_value": "1000"},
        follow_redirects=True,
    )
    client.post(
        "/accounts",
        data={"name": "Card", "account_type_id": card, "initial_value": "200"},
        follow_redirects=True,
    )
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"$800.00" in resp.data
