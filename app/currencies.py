"""Catalog of selectable display currencies.

Tallyworth stores amounts as integer cents and does not convert between
currencies; choosing a currency only changes the symbol shown in the UI.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    code: str
    name: str
    symbol: str


# A small set of common world currencies. Order is the display order in the
# selector. Symbols are kept simple; where a currency has no widely-recognised
# single-glyph symbol the ISO code (or a short form) is used.
CURRENCIES: tuple[Currency, ...] = (
    Currency("USD", "US Dollar", "$"),
    Currency("EUR", "Euro", "\u20ac"),
    Currency("GBP", "British Pound", "\u00a3"),
    Currency("JPY", "Japanese Yen", "\u00a5"),
    Currency("CNY", "Chinese Yuan", "\u00a5"),
    Currency("CAD", "Canadian Dollar", "$"),
    Currency("AUD", "Australian Dollar", "$"),
    Currency("CHF", "Swiss Franc", "CHF"),
    Currency("INR", "Indian Rupee", "\u20b9"),
    Currency("KRW", "South Korean Won", "\u20a9"),
    Currency("BRL", "Brazilian Real", "R$"),
    Currency("MXN", "Mexican Peso", "$"),
    Currency("SEK", "Swedish Krona", "kr"),
    Currency("NZD", "New Zealand Dollar", "$"),
    Currency("ZAR", "South African Rand", "R"),
)

CURRENCY_BY_CODE: dict[str, Currency] = {c.code: c for c in CURRENCIES}

DEFAULT_CURRENCY_CODE = "USD"


def get_currency(code: str | None) -> Currency:
    """Return the currency for a code, falling back to the default.

    Lookup is case-insensitive (e.g. "eur" resolves to EUR).
    """
    if code:
        normalized = code.strip().upper()
        if normalized in CURRENCY_BY_CODE:
            return CURRENCY_BY_CODE[normalized]
    return CURRENCY_BY_CODE[DEFAULT_CURRENCY_CODE]
