"""Monthly cashflow summary.

Sums income and expense entries to a simple in-the-green / in-the-red figure.
This is intentionally light: no budgeting, no per-category maths beyond totals.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from app.extensions import db
from app.models.cashflow import CashflowEntry, CashflowKind


@dataclass(frozen=True)
class CashflowSummary:
    income_cents: int
    expense_cents: int
    entry_count: int = 0

    @property
    def net_cents(self) -> int:
        return self.income_cents - self.expense_cents

    @property
    def in_green(self) -> bool:
        return self.net_cents >= 0

    @property
    def has_entries(self) -> bool:
        return self.entry_count > 0


def cashflow_summary() -> CashflowSummary:
    """Return total income and expense across all cashflow entries."""
    rows = db.session.execute(
        select(
            CashflowEntry.kind,
            func.coalesce(func.sum(CashflowEntry.amount_cents), 0),
            func.count(CashflowEntry.id),
        ).group_by(CashflowEntry.kind)
    ).all()
    totals = {kind: total for kind, total, _ in rows}
    count = sum(c for _, _, c in rows)
    return CashflowSummary(
        income_cents=totals.get(CashflowKind.income, 0),
        expense_cents=totals.get(CashflowKind.expense, 0),
        entry_count=count,
    )
