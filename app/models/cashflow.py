"""Monthly cashflow entries.

A light, budget-free indicator: income sources and individual expenses are
listed with their typical monthly amount. They are summed to tell the user
whether they are in the green (income covers expenses) or the red. Cashflow is
deliberately separate from net worth and carries no value history.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from app.extensions import db


def _utcnow() -> datetime:
    """Naive UTC timestamp, matching the DateTime column storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CashflowKind(enum.Enum):
    """Whether an entry is money coming in or going out."""

    income = "income"
    expense = "expense"


class CashflowEntry(db.Model):
    __tablename__ = "cashflow_entry"

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.Enum(CashflowKind), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        db.CheckConstraint("amount_cents >= 0", name="ck_cashflow_amount_nonneg"),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<CashflowEntry {self.kind.value} {self.name} {self.amount_cents}c>"
