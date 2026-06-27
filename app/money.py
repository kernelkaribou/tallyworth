"""Money parsing helpers. Monetary values are stored as integer cents."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation


class MoneyError(ValueError):
    """Raised when a money string cannot be parsed."""


def parse_money_to_cents(raw: str) -> int:
    """Parse a user-entered money string (e.g. "1,234.56" or "-50") to cents.

    Accepts an optional leading currency symbol, thousands separators, and a
    leading minus sign. Rejects more than two decimal places.
    """
    if raw is None:
        raise MoneyError("No value provided.")
    cleaned = raw.strip().replace(",", "").lstrip("$").strip()
    if cleaned in ("", "-", "+"):
        raise MoneyError("No value provided.")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise MoneyError(f"'{raw}' is not a valid amount.") from exc
    if amount.as_tuple().exponent < -2:
        raise MoneyError("Amounts cannot have more than two decimal places.")
    return int((amount * 100).to_integral_value())
