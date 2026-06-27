"""Account model and its running value snapshots."""
from __future__ import annotations

from datetime import datetime, timezone

from app.extensions import db
from app.models.account_type import Classification


def _utcnow() -> datetime:
    """Naive UTC timestamp, matching the DateTime column storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Account(db.Model):
    __tablename__ = "account"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    account_type_id = db.Column(
        db.Integer, db.ForeignKey("account_type.id"), nullable=False
    )
    archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    account_type = db.relationship("AccountType", back_populates="accounts")
    values = db.relationship(
        "AccountValue",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="AccountValue.recorded_at",
    )

    @property
    def latest_value(self) -> "AccountValue | None":
        """Most recent value snapshot, or None if no value recorded yet.

        Ties on ``recorded_at`` are broken by insertion order (id) so the most
        recently added snapshot wins.
        """
        if not self.values:
            return None
        return max(self.values, key=lambda v: (v.recorded_at, v.id or 0))

    @property
    def current_value_cents(self) -> int | None:
        latest = self.latest_value
        return latest.value_cents if latest else None

    @property
    def signed_value_cents(self) -> int:
        """Current value contribution to net worth (liabilities are negative)."""
        value = self.current_value_cents
        if value is None:
            return 0
        if self.account_type.classification == Classification.liability:
            return -value
        return value

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Account {self.name}>"


class AccountValue(db.Model):
    """A point-in-time value for an account (the running time series)."""

    __tablename__ = "account_value"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer, db.ForeignKey("account.id"), nullable=False, index=True
    )
    value_cents = db.Column(db.Integer, nullable=False)
    recorded_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    account = db.relationship("Account", back_populates="values")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AccountValue account={self.account_id} {self.value_cents}c>"
