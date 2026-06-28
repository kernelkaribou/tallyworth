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


def test_failed_create_preserves_selected_type(app, client):
    with app.app_context():
        savings = _type_id("Savings")
    resp = client.post(
        "/accounts",
        data={"name": "", "account_type_id": savings, "initial_value": "50"},
    )
    assert resp.status_code == 400
    body = resp.data.decode()
    # The chosen type stays selected so the user does not have to re-pick it.
    start = body.index(f'value="{savings}"')
    end = body.index("</option>", start)
    assert "selected" in body[start:end]
    # The entered starting value is preserved too.
    assert 'value="50"' in body


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


def test_account_type_creation_route_is_gone(app, client):
    # Account types are a fixed built-in taxonomy; the create endpoint is removed.
    resp = client.post(
        "/account-types",
        data={"name": "Pension", "classification": "asset"},
    )
    assert resp.status_code in (404, 405)
    with app.app_context():
        assert AccountType.query.filter_by(name="Pension").first() is None


def test_add_value_rejects_negative_liability(app, client):
    with app.app_context():
        card = _type_id("Credit Card")
    client.post(
        "/accounts",
        data={"name": "Visa", "account_type_id": card},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Visa").first().id
    resp = client.post(
        f"/accounts/{account_id}/values", data={"value": "-50"}, follow_redirects=True
    )
    assert b"positive number" in resp.data
    with app.app_context():
        assert db.session.get(Account, account_id).current_value_cents is None


def test_add_value_allows_negative_asset(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    client.post(
        "/accounts",
        data={"name": "Overdrawn", "account_type_id": checking},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Overdrawn").first().id
    client.post(
        f"/accounts/{account_id}/values", data={"value": "-25"}, follow_redirects=True
    )
    with app.app_context():
        assert db.session.get(Account, account_id).current_value_cents == -2500


def test_add_value_handles_inf_without_crashing(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    client.post(
        "/accounts",
        data={"name": "Inf", "account_type_id": checking},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Inf").first().id
    resp = client.post(
        f"/accounts/{account_id}/values", data={"value": "inf"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"not a valid amount" in resp.data


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


def test_edit_account_form_renders(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    client.post(
        "/accounts",
        data={"name": "Old Name", "account_type_id": checking, "initial_value": "100"},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Old Name").one().id
    resp = client.get(f"/accounts/{account_id}/edit")
    assert resp.status_code == 200
    assert b"Old Name" in resp.data


def test_update_account_renames_and_changes_type(app, client):
    with app.app_context():
        checking = _type_id("Checking")
        savings = _type_id("Savings")
    # No recorded values yet, so the type is still editable.
    client.post(
        "/accounts",
        data={"name": "Rename Me", "account_type_id": checking},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Rename Me").one().id
    resp = client.post(
        f"/accounts/{account_id}/edit",
        data={"name": "Renamed", "account_type_id": savings},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        account = db.session.get(Account, account_id)
        assert account.name == "Renamed"
        assert account.account_type.name == "Savings"


def test_account_type_locked_once_values_exist(app, client):
    with app.app_context():
        checking = _type_id("Checking")
        savings = _type_id("Savings")
    client.post(
        "/accounts",
        data={"name": "Locked", "account_type_id": checking, "initial_value": "100"},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Locked").one().id
    # The edit form should not offer a type selector once history exists.
    form = client.get(f"/accounts/{account_id}/edit")
    assert b"The type is locked" in form.data
    # A forged type change is ignored; only the name updates.
    resp = client.post(
        f"/accounts/{account_id}/edit",
        data={"name": "Still Checking", "account_type_id": savings},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        account = db.session.get(Account, account_id)
        assert account.name == "Still Checking"
        assert account.account_type.name == "Checking"


def test_update_account_requires_name(app, client):
    with app.app_context():
        checking = _type_id("Checking")
    client.post(
        "/accounts",
        data={"name": "Keep", "account_type_id": checking, "initial_value": "100"},
        follow_redirects=True,
    )
    with app.app_context():
        account_id = Account.query.filter_by(name="Keep").one().id
    resp = client.post(
        f"/accounts/{account_id}/edit",
        data={"name": "", "account_type_id": checking},
    )
    assert resp.status_code == 400
    assert b"required" in resp.data
    with app.app_context():
        assert db.session.get(Account, account_id).name == "Keep"
