"""Smoke tests for the application scaffold."""
from __future__ import annotations


def test_index_ok(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Tallyworth" in resp.data


def test_healthz_ok(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_dashboard_has_h1(client):
    resp = client.get("/")
    assert b"<h1" in resp.data and b">Dashboard</h1>" in resp.data


def test_active_nav_marked(client):
    # The current section's nav link carries aria-current for orientation.
    resp = client.get("/cashflow")
    assert b'aria-current="page"' in resp.data
    assert resp.data.count(b'aria-current="page"') == 1
