"""Tests for money parsing."""
from __future__ import annotations

import pytest

from app.money import MoneyError, parse_money_to_cents


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("100", 10000),
        ("100.50", 10050),
        ("1,234.56", 123456),
        ("$2,000", 200000),
        ("-50", -5000),
        ("0", 0),
        ("0.01", 1),
        ("  42.00 ", 4200),
    ],
)
def test_parse_valid(raw, expected):
    assert parse_money_to_cents(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "   ", "abc", "1.234", "1.2.3", "-", "$", "inf", "-inf", "nan", "1e3", ".5", "5."]
)
def test_parse_invalid(raw):
    with pytest.raises(MoneyError):
        parse_money_to_cents(raw)


def test_parse_rejects_too_large():
    with pytest.raises(MoneyError):
        parse_money_to_cents("9" * 20)
