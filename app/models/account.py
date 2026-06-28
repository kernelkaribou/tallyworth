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
    def tracks_loan(self) -> bool:
        """Whether this account records a loan balance alongside its value."""
        return self.account_type.tracks_loan

    @property
    def current_loan_cents(self) -> int | None:
        """Latest recorded loan balance, or None if not loan-tracking / unset."""
        latest = self.latest_value
        if latest is None:
            return None
        return latest.loan_cents

    @property
    def equity_cents(self) -> int | None:
        """Owner's equity: market value minus any outstanding loan.

        For accounts that do not track a loan this is just the current value.
        Returns None when no value has been recorded yet.
        """
        latest = self.latest_value
        if latest is None:
            return None
        if self.account_type.tracks_loan:
            return latest.value_cents - (latest.loan_cents or 0)
        return latest.value_cents

    @property
    def signed_value_cents(self) -> int:
        """Contribution to net worth (liabilities negative, equity for loans)."""
        latest = self.latest_value
        if latest is None:
            return 0
        if self.account_type.classification == Classification.liability:
            return -latest.value_cents
        if self.account_type.tracks_loan:
            return latest.value_cents - (latest.loan_cents or 0)
        return latest.value_cents

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<Account {self.name}>"


class AccountValue(db.Model):
    """A point-in-time value for an account (the running time series).

    For loan-tracking accounts (e.g. a car or house) ``value_cents`` is the
    market value and ``loan_cents`` is the outstanding loan balance at that
    moment; equity is the difference. ``loan_cents`` is null for accounts that
    do not track a loan.
    """

    __tablename__ = "account_value"

    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(
        db.Integer, db.ForeignKey("account.id"), nullable=False, index=True
    )
    value_cents = db.Column(db.Integer, nullable=False)
    loan_cents = db.Column(db.Integer, nullable=True)
    recorded_at = db.Column(db.DateTime, nullable=False, default=_utcnow, index=True)

    __table_args__ = (
        db.CheckConstraint(
            "loan_cents IS NULL OR loan_cents >= 0",
            name="ck_account_value_loan_nonneg",
        ),
    )

    account = db.relationship("Account", back_populates="values")

    @property
    def equity_cents(self) -> int:
        """Market value minus any loan balance for this snapshot."""
        return self.value_cents - (self.loan_cents or 0)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AccountValue account={self.account_id} {self.value_cents}c>"
