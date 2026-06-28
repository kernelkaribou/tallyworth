"""Tests for the conservative net worth trend projection."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.networth import (
    PROJECTION_MAX_HORIZON_DAYS,
    PROJECTION_MIN_SPAN_DAYS,
    NetWorthPoint,
    _theil_sen_slope,
    project_net_worth,
)


def _point(day: int, net_cents: int) -> NetWorthPoint:
    return NetWorthPoint(
        recorded_at=datetime(2026, 1, 1) + timedelta(days=day),
        net_cents=net_cents,
    )


def test_projection_needs_at_least_three_points():
    assert project_net_worth([]) == []
    assert project_net_worth([_point(0, 100)]) == []
    assert project_net_worth([_point(0, 100), _point(60, 200)]) == []


def test_projection_needs_minimum_history_span():
    # Three points but only a few days apart -> no projection.
    points = [_point(0, 100000), _point(2, 150000), _point(4, 200000)]
    assert project_net_worth(points) == []


def test_short_history_under_min_span_has_no_projection():
    span = PROJECTION_MIN_SPAN_DAYS - 1
    points = [_point(0, 0), _point(span // 2, 1000), _point(span, 2000)]
    assert project_net_worth(points) == []


def test_projection_returns_anchor_and_future_endpoint():
    points = [_point(0, 100000), _point(30, 200000), _point(60, 300000)]
    projection = project_net_worth(points)

    assert len(projection) == 2
    anchor, end = projection
    # Anchor matches the last actual point so the dashed line connects.
    assert anchor.recorded_at == points[-1].recorded_at
    assert anchor.net_cents == points[-1].net_cents
    # Endpoint is in the future and follows the upward trend.
    assert end.recorded_at > anchor.recorded_at
    assert end.net_cents > anchor.net_cents


def test_projection_follows_slope():
    # +100,000 cents per 30 days, perfectly linear.
    points = [_point(0, 0), _point(30, 100000), _point(60, 200000)]
    anchor, end = project_net_worth(points)

    horizon_days = min(60, PROJECTION_MAX_HORIZON_DAYS)
    horizon_delta = (end.recorded_at - anchor.recorded_at).days
    assert abs(horizon_delta - horizon_days) <= 1

    expected = round(200000 + (100000 / (30 * 86400)) * horizon_days * 86400)
    assert abs(end.net_cents - expected) <= 2


def test_projection_horizon_never_exceeds_max():
    # A long, steady history caps the horizon at the maximum.
    points = [_point(0, 0), _point(400, 40000), _point(800, 80000)]
    anchor, end = project_net_worth(points)
    horizon_days = (end.recorded_at - anchor.recorded_at).days
    assert horizon_days <= PROJECTION_MAX_HORIZON_DAYS


def test_flat_history_projects_flat_trend():
    points = [_point(0, 50000), _point(30, 50000), _point(60, 50000)]
    anchor, end = project_net_worth(points)
    assert anchor.net_cents == 50000
    assert end.net_cents == 50000


def test_theil_sen_slope_ignores_a_single_outlier():
    xs = [0.0, 1.0, 2.0, 3.0, 4.0]
    clean = [0.0, 10.0, 20.0, 30.0, 40.0]
    with_outlier = [0.0, 10.0, 1000.0, 30.0, 40.0]
    # Median-of-slopes is unmoved by the single spike (OLS would be skewed).
    assert _theil_sen_slope(xs, clean) == 10.0
    assert _theil_sen_slope(xs, with_outlier) == 10.0


def test_dashboard_shows_projection_when_enough_history(client, app):
    from app.extensions import db
    from app.models import Account, AccountType, AccountValue

    with app.app_context():
        checking_type = AccountType.query.filter_by(name="Checking").first()
        account = Account(name="Savings", account_type=checking_type)
        db.session.add(account)
        for i in range(3):
            account.values.append(
                AccountValue(
                    value_cents=100000 + i * 50000,
                    recorded_at=datetime(2026, 1, 1) + timedelta(days=30 * i),
                )
            )
        db.session.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    assert b'data-projection-source="networth-projection"' in resp.data
    assert b'id="networth-projection"' in resp.data


def test_dashboard_hides_projection_with_too_little_history(client, app):
    from app.extensions import db
    from app.models import Account, AccountType, AccountValue

    with app.app_context():
        checking_type = AccountType.query.filter_by(name="Checking").first()
        account = Account(name="Wallet", account_type=checking_type)
        db.session.add(account)
        account.values.append(
            AccountValue(value_cents=100000, recorded_at=datetime(2026, 1, 1))
        )
        db.session.commit()

    resp = client.get("/")
    assert resp.status_code == 200
    assert b"data-projection-source" not in resp.data
    assert b'id="networth-projection"' not in resp.data
