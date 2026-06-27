"""Net worth calculations.

Current net worth is the sum of each active account's latest value, where
liabilities count as negative. Accounts with no recorded value contribute zero.
Archived accounts are excluded from the current figure.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.account import Account
from app.models.account_type import Classification


@dataclass(frozen=True)
class NetWorthSummary:
    assets_cents: int
    liabilities_cents: int

    @property
    def net_cents(self) -> int:
        return self.assets_cents - self.liabilities_cents


def current_net_worth(accounts: list[Account] | None = None) -> NetWorthSummary:
    """Compute the current net worth summary across active accounts."""
    if accounts is None:
        accounts = Account.query.filter_by(archived=False).all()

    assets = 0
    liabilities = 0
    for account in accounts:
        if account.archived:
            continue
        value = account.current_value_cents
        if value is None:
            continue
        if account.account_type.classification == Classification.liability:
            liabilities += value
        else:
            assets += value
    return NetWorthSummary(assets_cents=assets, liabilities_cents=liabilities)
