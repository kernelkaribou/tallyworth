"""Net worth calculations.

Current net worth is the sum of each active account's latest value, where
liabilities count as negative. Accounts with no recorded value contribute zero.
Archived accounts are excluded from the current figure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

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


@dataclass(frozen=True)
class NetWorthPoint:
    recorded_at: datetime
    net_cents: int


def latest_snapshot_map(
    account_ids: list[int] | None = None,
) -> dict[int, tuple[int, int | None]]:
    """Return {account_id: (value_cents, loan_cents)} for each latest snapshot.

    The latest snapshot is the one with the greatest recorded_at, ties broken by
    insertion id. Accounts with no values are absent from the map.
    """
    row_number = (
        func.row_number()
        .over(
            partition_by=AccountValue.account_id,
            order_by=(AccountValue.recorded_at.desc(), AccountValue.id.desc()),
        )
        .label("rn")
    )
    ranked = select(
        AccountValue.account_id,
        AccountValue.value_cents,
        AccountValue.loan_cents,
        row_number,
    )
    if account_ids is not None:
        if not account_ids:
            return {}
        ranked = ranked.where(AccountValue.account_id.in_(account_ids))
    ranked = ranked.subquery()

    latest = select(
        ranked.c.account_id, ranked.c.value_cents, ranked.c.loan_cents
    ).where(ranked.c.rn == 1)
    return {
        account_id: (value, loan)
        for account_id, value, loan in db.session.execute(latest)
    }


def latest_value_cents_map(account_ids: list[int] | None = None) -> dict[int, int]:
    """Return {account_id: latest market value_cents} (loan ignored)."""
    return {
        account_id: value
        for account_id, (value, _loan) in latest_snapshot_map(account_ids).items()
    }


def _contribution_cents(account: Account, value_cents: int, loan_cents: int | None) -> int:
    """Signed net-worth contribution for one account's latest snapshot."""
    if account.account_type.classification == Classification.liability:
        return -value_cents
    if account.account_type.tracks_loan:
        return value_cents - (loan_cents or 0)
    return value_cents


def display_value_map(
    accounts: list[Account],
    snapshots: dict[int, tuple[int, int | None]] | None = None,
) -> dict[int, int]:
    """Per-account value to display: equity for loan accounts, else market value.

    Liabilities keep their positive magnitude (the UI colours them separately).
    """
    if snapshots is None:
        snapshots = latest_snapshot_map([a.id for a in accounts])
    result: dict[int, int] = {}
    for account in accounts:
        snap = snapshots.get(account.id)
        if snap is None:
            continue
        value_cents, loan_cents = snap
        if account.account_type.tracks_loan:
            result[account.id] = value_cents - (loan_cents or 0)
        else:
            result[account.id] = value_cents
    return result


def current_net_worth(
    accounts: list[Account] | None = None,
    snapshots: dict[int, tuple[int, int | None]] | None = None,
) -> NetWorthSummary:
    """Compute the current net worth summary across active accounts."""
    if accounts is None:
        accounts = (
            Account.query.options(selectinload(Account.account_type))
            .filter_by(archived=False)
            .all()
        )
    if snapshots is None:
        snapshots = latest_snapshot_map(
            [a.id for a in accounts if not a.archived]
        )

    assets = 0
    liabilities = 0
    for account in accounts:
        if account.archived:
            continue
        snap = snapshots.get(account.id)
        if snap is None:
            continue
        value_cents, loan_cents = snap
        if account.account_type.classification == Classification.liability:
            liabilities += value_cents
        elif account.account_type.tracks_loan:
            assets += value_cents - (loan_cents or 0)
        else:
            assets += value_cents
    return NetWorthSummary(assets_cents=assets, liabilities_cents=liabilities)


def net_worth_series(accounts: list[Account] | None = None) -> list[NetWorthPoint]:
    """Return net worth over time using a forward-fill of each account's value.

    The series has one point per distinct timestamp at which any active account
    recorded a value. At each timestamp every account contributes its most recent
    value as of that moment (liabilities negative, equity for loan-tracking
    accounts); accounts with no value yet contribute zero. Because the last value
    is carried forward, the final point equals :func:`current_net_worth`. Archived
    accounts are excluded so the series stays consistent with the current figure.
    """
    if accounts is None:
        accounts = (
            Account.query.options(selectinload(Account.account_type))
            .filter_by(archived=False)
            .all()
        )

    active = {a.id: a for a in accounts if not a.archived}
    if not active:
        return []

    rows = db.session.execute(
        select(
            AccountValue.account_id,
            AccountValue.value_cents,
            AccountValue.loan_cents,
            AccountValue.recorded_at,
        )
        .where(AccountValue.account_id.in_(active.keys()))
        .order_by(AccountValue.recorded_at.asc(), AccountValue.id.asc())
    ).all()
    if not rows:
        return []

    current: dict[int, int] = {}
    points: list[NetWorthPoint] = []
    last_ts: datetime | None = None
    for account_id, value_cents, loan_cents, recorded_at in rows:
        if last_ts is not None and recorded_at != last_ts:
            points.append(
                NetWorthPoint(recorded_at=last_ts, net_cents=sum(current.values()))
            )
        current[account_id] = _contribution_cents(
            active[account_id], value_cents, loan_cents
        )
        last_ts = recorded_at

    points.append(NetWorthPoint(recorded_at=last_ts, net_cents=sum(current.values())))
    return points
