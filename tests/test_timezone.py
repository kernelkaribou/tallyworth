"""Tests for TZ-driven display: storage stays UTC, presentation localizes."""
from __future__ import annotations

from datetime import datetime

from flask import render_template_string

from app import create_app
from app.config import TestConfig


def _render(template, tz, value):
    class Cfg(TestConfig):
        DISPLAY_TIMEZONE = tz

    app = create_app(Cfg)
    with app.test_request_context():
        return render_template_string(template, dt=value)


# A fixed naive UTC timestamp (matches how snapshots are stored).
UTC_DT = datetime(2026, 6, 26, 2, 18)


def test_localdt_defaults_to_utc():
    assert _render("{{ dt | localdt }}", "UTC", UTC_DT) == "2026-06-26 02:18 UTC"


def test_localdt_shifts_to_configured_zone():
    # 02:18 UTC is the prior evening in New York (EDT, UTC-4).
    assert _render("{{ dt | localdt }}", "America/New_York", UTC_DT) == "2026-06-25 22:18 EDT"


def test_localdt_unknown_zone_falls_back_to_utc():
    assert _render("{{ dt | localdt }}", "Not/AZone", UTC_DT) == "2026-06-26 02:18 UTC"


def test_localdt_handles_none():
    assert _render("{{ dt | localdt }}", "UTC", None) == "-"


def test_localdt_custom_format():
    assert _render("{{ dt | localdt('%b %d, %Y') }}", "America/New_York", UTC_DT) == "Jun 25, 2026"


def test_display_timezone_injected():
    assert _render("{{ display_timezone }}", "America/New_York", UTC_DT) == "America/New_York"


def test_display_timezone_falls_back_when_invalid():
    assert _render("{{ display_timezone }}", "Not/AZone", UTC_DT) == "UTC"
