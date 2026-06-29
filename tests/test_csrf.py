"""CSRF protection is enforced on state-changing POST routes.

The default test suite disables CSRF (TestConfig.WTF_CSRF_ENABLED = False) so the
other tests can post forms directly. These tests build a CSRF-enabled app to
confirm the protection is actually wired up: tokenless posts are rejected, the
token is rendered into forms, and a posted token is accepted.
"""
from __future__ import annotations

import pytest

from app import create_app
from app.config import TestConfig
from app.extensions import db as _db
from app.seed import seed_account_types


class CsrfConfig(TestConfig):
    WTF_CSRF_ENABLED = True
    SECRET_KEY = "csrf-test-key"


@pytest.fixture()
def csrf_client():
    app = create_app(CsrfConfig)
    with app.app_context():
        _db.create_all()
        seed_account_types()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


def test_post_without_token_is_rejected(csrf_client):
    resp = csrf_client.post(
        "/cashflow", data={"kind": "income", "name": "Salary", "amount": "10"}
    )
    assert resp.status_code == 400


def test_forms_render_csrf_token(csrf_client):
    resp = csrf_client.get("/accounts/new")
    assert resp.status_code == 200
    assert b'name="csrf_token"' in resp.data


def test_post_with_token_is_accepted(csrf_client):
    page = csrf_client.get("/cashflow")
    token = _extract_token(page.data)
    resp = csrf_client.post(
        "/cashflow",
        data={
            "csrf_token": token,
            "kind": "income",
            "name": "Salary",
            "amount": "10",
        },
    )
    assert resp.status_code == 302


def _extract_token(html: bytes) -> str:
    marker = b'name="csrf_token" value="'
    start = html.index(marker) + len(marker)
    end = html.index(b'"', start)
    return html[start:end].decode()
