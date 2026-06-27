"""Net worth calculations.

Current net worth is the sum of each active account's latest value, where
liabilities count as negative. Accounts with no recorded value contribute zero.
Archived accounts are excluded from the current figure.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select

from app.extensions import db
from app.models.account import Account, AccountValue
from app.models.account_type import Classification


@dataclass(frozen=True)
class NetWorthSummary:
    assets_cents: int
    liabilities_cents: int

    @property
    def net_cents(self) -> int:
        return self.assets_cents - self.liabilities_cents


def latest_value_cents_map(account_ids: list[int] | None = None) -> dict[int, int]:
    """Return {account_id: latest value_cents} using a single window query.

    The latest snapshot is the one with the greatest recorded_at, ties broken by
    insertion id. Accounts with no values are simply absent from the map.
    """
    row_number = (
        func.row_number()
        .over(
            partition_by=AccountValue.account_id,
            order_by=(AccountValue.recorded_at.desc(), AccountValue.id.desc()),
        )
        .label("rn")
    )
    ranked = select(AccountValue.account_id, AccountValue.value_cents, row_number)
    if account_ids is not None:
        if not account_ids:
            return {}
        ranked = ranked.where(AccountValue.account_id.in_(account_ids))
    ranked = ranked.subquery()

    latest = select(ranked.c.account_id, ranked.c.value_cents).where(ranked.c.rn == 1)
    return {account_id: value for account_id, value in db.session.execute(latest)}


def current_net_worth(
    accounts: list[Account] | None = None,
    values_map: dict[int, int] | None = None,
) -> NetWorthSummary:
    """Compute the current net worth summary across active accounts."""
    if accounts is None:
        accounts = Account.query.filter_by(archived=False).all()
    if values_map is None:
        values_map = latest_value_cents_map(
            [a.id for a in accounts if not a.archived]
        )

    assets = 0
    liabilities = 0
    for account in accounts:
        if account.archived:
            continue
        value = values_map.get(account.id)
        if value is None:
            continue
        if account.account_type.classification == Classification.liability:
            liabilities += value
        else:
            assets += value
    return NetWorthSummary(assets_cents=assets, liabilities_cents=liabilities)
