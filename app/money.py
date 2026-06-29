"""Money parsing helpers. Monetary values are stored as integer cents."""
from __future__ import annotations

import re
from decimal import Decimal

# Optional sign, digits, optional 1-2 decimal places. Currency symbol and
# thousands separators are stripped before matching.
_MONEY_RE = re.compile(r"[+-]?\d+(\.\d{1,2})?")

# Guard against absurd values; keeps the stored cents well within a 64-bit int.
MAX_CENTS = 10**15


class MoneyError(ValueError):
    """Raised when a money string cannot be parsed."""


def parse_money_to_cents(raw: str | None) -> int:
    """Parse a user-entered money string (e.g. "1,234.56" or "-50") to cents.

    Accepts an optional currency symbol, thousands separators, a leading sign,
    and at most two decimal places. Rejects empty input, non-numeric text,
    scientific notation, and the special values inf/nan.
    """
    if raw is None:
        raise MoneyError("No value provided.")
    cleaned = raw.strip().replace("$", "").replace(",", "").strip()
    if cleaned == "":
        raise MoneyError("No value provided.")
    if not _MONEY_RE.fullmatch(cleaned):
        raise MoneyError(f"'{raw}' is not a valid amount.")
    cents = int((Decimal(cleaned) * 100).to_integral_value())
    if abs(cents) > MAX_CENTS:
        raise MoneyError("Amount is too large.")
    return cents
