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
