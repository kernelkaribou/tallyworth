"""Net worth calculations.

Current net worth is the sum of each active account's latest value, where
liabilities count as negative. Accounts with no recorded value contribute zero.
Archived accounts are excluded from the current figure.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median

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


@dataclass(frozen=True)
class AccountTrend:
    """Trend summary for one account's tile on the dashboard.

    ``current_cents`` / ``previous_cents`` are the latest two display values
    (equity for loan-tracking accounts, market value otherwise; liabilities keep
    their positive magnitude). ``direction`` describes the raw movement of that
    number, while ``improved`` says whether the change is good for net worth (so
    a paid-down liability counts as an improvement even though the number fell).
    ``spark_points`` is a ready-to-draw SVG polyline string over a 100x28 box.
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
    """Normalise display values into an SVG polyline string over a 100x28 box."""
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
        if account.account_type.tracks_loan:
            display = value_cents - (loan_cents or 0)
        else:
            display = value_cents
        series[account_id].append(display)

    for account_id, values in series.items():
        account = by_id[account_id]
        is_liability = (
            account.account_type.classification == Classification.liability
        )
        current = values[-1] if values else None
        previous = values[-2] if len(values) >= 2 else None

        if previous is None or current is None:
            direction = "none"
            improved: bool | None = None
            delta: int | None = None
        else:
            delta = current - previous
            if delta > 0:
                direction = "up"
            elif delta < 0:
                direction = "down"
            else:
                direction = "flat"
            if delta == 0:
                improved = None
            else:
                # For liabilities a smaller balance is better; for assets larger.
                improved = (delta < 0) if is_liability else (delta > 0)

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


# Guardrails for the trend projection. Kept deliberately conservative: a short,
# clearly-dashed estimate from a robust slope, not a long speculative forecast.
PROJECTION_MIN_POINTS = 3
# Require a real stretch of history (not just three rapid updates) before
# extrapolating, and never project further ahead than we have looked back.
PROJECTION_MIN_SPAN_DAYS = 30
PROJECTION_MAX_HORIZON_DAYS = 180
# Suppress the projection when extrapolating would land more than this multiple
# of the observed net-worth range away from the latest value (runaway slope).
PROJECTION_MAX_RANGE_MULTIPLE = 3
_DAY_SECONDS = 86400


def _epoch_seconds(dt: datetime) -> float:
    """Epoch seconds for a naive-UTC datetime (matches the chart's x convention)."""
    return dt.replace(tzinfo=timezone.utc).timestamp()


def _theil_sen_slope(xs: list[float], ys: list[float]) -> float | None:
    """Median of all pairwise slopes (Theil-Sen estimator).

    This is robust to outliers, so a single large jump (e.g. adding an existing
    account for the first time) or a cluster of rapid updates does not dominate
    the trend the way an ordinary least-squares fit would. Returns ``None`` when
    no pair has a distinct x value.
    """
    slopes: list[float] = []
    n = len(xs)
    for i in range(n):
        for j in range(i + 1, n):
            dx = xs[j] - xs[i]
            if dx != 0:
                slopes.append((ys[j] - ys[i]) / dx)
    if not slopes:
        return None
    return median(slopes)


def project_net_worth(points: list[NetWorthPoint]) -> list[NetWorthPoint]:
    """Return a short trend projection extending the historical series.

    A robust (Theil-Sen median) slope is fitted to the historical net-worth
    points and carried forward from the most recent actual point. The projection
    is intentionally conservative:

    * it requires at least ``PROJECTION_MIN_POINTS`` real points spanning at
      least ``PROJECTION_MIN_SPAN_DAYS`` of history;
    * it uses a median-of-pairwise-slopes estimator so a single jump or a burst
      of updates cannot dominate the trend;
    * it is anchored to the latest actual value (so the dashed line connects to
      the solid line with no jump);
    * the horizon never exceeds the observed history span and is capped at
      ``PROJECTION_MAX_HORIZON_DAYS``;
    * a runaway extrapolation (more than ``PROJECTION_MAX_RANGE_MULTIPLE`` times
      the observed range away from the latest value) is suppressed entirely.

    The result is a two-point list (anchor + future endpoint) suitable for
    drawing a dashed continuation, or an empty list when the data is too sparse,
    too short, or would produce an implausible projection.
    """
    if len(points) < PROJECTION_MIN_POINTS:
        return []

    xs = [_epoch_seconds(p.recorded_at) for p in points]
    ys = [float(p.net_cents) for p in points]
    span = xs[-1] - xs[0]
    if span < PROJECTION_MIN_SPAN_DAYS * _DAY_SECONDS:
        return []

    slope = _theil_sen_slope(xs, ys)
    if slope is None:
        return []

    horizon = min(span, PROJECTION_MAX_HORIZON_DAYS * _DAY_SECONDS)

    last_x = xs[-1]
    last_y = points[-1].net_cents
    end_x = last_x + horizon
    end_y = round(last_y + slope * horizon)

    value_range = max(ys) - min(ys)
    if value_range > 0 and abs(end_y - last_y) > PROJECTION_MAX_RANGE_MULTIPLE * value_range:
        return []

    end_dt = datetime.fromtimestamp(end_x, tz=timezone.utc).replace(tzinfo=None)

    return [
        NetWorthPoint(recorded_at=points[-1].recorded_at, net_cents=last_y),
        NetWorthPoint(recorded_at=end_dt, net_cents=end_y),
    ]
