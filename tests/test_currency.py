"""Tests for env-driven currency symbol resolution."""
from __future__ import annotations

import pytest

from app import create_app
from app.config import TestConfig
from app.currencies import get_currency


@pytest.mark.parametrize(
    "code,symbol",
    [
        ("USD", "$"),
        ("EUR", "\u20ac"),
        ("GBP", "\u00a3"),
        ("JPY", "\u00a5"),
        ("ZZZ", "$"),  # unknown code falls back to USD
        ("eur", "\u20ac"),  # lookup is case-insensitive
        (None, "$"),
    ],
)
def test_get_currency_symbol(code, symbol):
    assert get_currency(code).symbol == symbol


def _symbol_for(**overrides):
    class Cfg(TestConfig):
        pass

    for key, value in overrides.items():
        setattr(Cfg, key, value)
    app = create_app(Cfg)
    with app.test_request_context():
        from flask import render_template_string

        return render_template_string("{{ currency_symbol }}")


def test_default_currency_drives_symbol():
    assert _symbol_for(DEFAULT_CURRENCY="EUR", CURRENCY_SYMBOL=None) == "\u20ac"


def test_unknown_default_currency_falls_back_to_usd():
    assert _symbol_for(DEFAULT_CURRENCY="ZZZ", CURRENCY_SYMBOL=None) == "$"


def test_currency_symbol_override_takes_precedence():
    assert _symbol_for(DEFAULT_CURRENCY="EUR", CURRENCY_SYMBOL="Fr") == "Fr"


def test_money_filter_uses_resolved_symbol():
    class Cfg(TestConfig):
        DEFAULT_CURRENCY = "GBP"
        CURRENCY_SYMBOL = None

    app = create_app(Cfg)
    with app.test_request_context():
        from flask import render_template_string

        assert render_template_string("{{ 123456 | money }}") == "\u00a31,234.56"


def test_money_filter_puts_sign_before_symbol():
    # A negative amount (e.g. an underwater equity or negative net worth) should
    # read as "-$50.00", not "$-50.00".
    app = create_app(TestConfig)
    with app.test_request_context():
        from flask import render_template_string

        assert render_template_string("{{ -5000 | money }}") == "-$50.00"
        assert render_template_string("{{ 0 | money }}") == "$0.00"

