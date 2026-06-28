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


def net_worth_impact_cents(account: Account, value_cents: int, loan_cents: int | None) -> int:
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


@dataclass(frozen=True)
class AccountTrend:
    """Trend summary for one account's tile on the dashboard.

    Everything here is framed by **net-worth impact** (the signed contribution of
    the account: assets positive, liabilities negative, loan-tracking assets use
    equity). ``current_cents`` / ``previous_cents`` are the latest two impact
    values. ``direction`` is the movement of that impact, so ``up`` always means
    the account improved your net worth (a paid-down liability moves up toward
    zero). ``improved`` mirrors that (True for up, False for down, None when
    flat). ``delta_cents`` is the change in impact (positive == improvement).
    ``spark_points`` is a ready-to-draw SVG polyline of the impact series over a
    100x28 box.
    """

    direction: str  # "up" | "down" | "flat" | "none"
    improved: bool | None
    current_cents: int | None
    previous_cents: int | None
    delta_cents: int | None
    spark_points: str | None

    @property
    def has_history(self) -> bool:
        return self.previous_cents is not None


_SPARK_WIDTH = 100.0
_SPARK_HEIGHT = 28.0
_SPARK_PAD = 3.0


def _spark_polyline(values: list[int]) -> str | None:
    """Normalise an impact series into an SVG polyline string over a 100x28 box."""
    if len(values) < 2:
        return None
    lo = min(values)
    hi = max(values)
    span = hi - lo
    usable = _SPARK_HEIGHT - 2 * _SPARK_PAD
    step = _SPARK_WIDTH / (len(values) - 1)
    coords = []
    for i, v in enumerate(values):
        x = i * step
        if span == 0:
            y = _SPARK_HEIGHT / 2
        else:
            y = _SPARK_PAD + (1 - (v - lo) / span) * usable
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


def account_trends(accounts: list[Account]) -> dict[int, AccountTrend]:
    """Return {account_id: AccountTrend} for the given accounts.

    All value snapshots are loaded in a single query and grouped per account, so
    this is safe to call for the whole dashboard without N+1 queries. Accounts
    with no snapshots get a "none" trend with no sparkline.
    """
    by_id = {a.id: a for a in accounts}
    trends: dict[int, AccountTrend] = {}
    if not by_id:
        return trends

    rows = db.session.execute(
        select(
            AccountValue.account_id,
            AccountValue.value_cents,
            AccountValue.loan_cents,
        )
        .where(AccountValue.account_id.in_(by_id.keys()))
        .order_by(AccountValue.recorded_at.asc(), AccountValue.id.asc())
    ).all()

    series: dict[int, list[int]] = {aid: [] for aid in by_id}
    for account_id, value_cents, loan_cents in rows:
        account = by_id[account_id]
        series[account_id].append(
            net_worth_impact_cents(account, value_cents, loan_cents)
        )

    for account_id, values in series.items():
        current = values[-1] if values else None
        previous = values[-2] if len(values) >= 2 else None

        if previous is None or current is None:
            direction = "none"
            improved: bool | None = None
            delta: int | None = None
        else:
            # Series is net-worth impact, so a rise is always an improvement
            # (a paid-down liability moves up toward zero).
            delta = current - previous
            if delta > 0:
                direction = "up"
                improved = True
            elif delta < 0:
                direction = "down"
                improved = False
            else:
                direction = "flat"
                improved = None

        trends[account_id] = AccountTrend(
            direction=direction,
            improved=improved,
            current_cents=current,
            previous_cents=previous,
            delta_cents=delta,
            spark_points=_spark_polyline(values),
        )
    return trends


def net_worth_series(accounts: list[Account] | None = None) -> list[NetWorthPoint]:
    """Return net worth over time using a forward-fill of each account's value.

    The series has one point per calendar date on which any active account
    recorded a value; when a date has several snapshots the latest one wins. At
    each date every account contributes its most recent value as of that moment
    (liabilities negative, equity for loan-tracking accounts); accounts with no
    value yet contribute zero. Because the last value is carried forward, the
    final point equals :func:`current_net_worth`. Archived accounts are excluded
    so the series stays consistent with the current figure.
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
        current[account_id] = net_worth_impact_cents(
            active[account_id], value_cents, loan_cents
        )
        last_ts = recorded_at

    points.append(NetWorthPoint(recorded_at=last_ts, net_cents=sum(current.values())))

    # Collapse to one point per calendar date, keeping the latest entry that
    # day. Net worth is tracked by day, not by time, so multiple same-date
    # snapshots should surface as a single point at that date's most recent
    # value. Points are ascending by timestamp, so same-date points are adjacent.
    collapsed: list[NetWorthPoint] = []
    for point in points:
        if collapsed and collapsed[-1].recorded_at.date() == point.recorded_at.date():
            collapsed[-1] = point
        else:
            collapsed.append(point)
    return collapsed
