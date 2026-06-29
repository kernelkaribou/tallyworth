"""Account type taxonomy.

An account type carries the financial classification that drives net worth maths
(assets are positive, liabilities are negative) and a flag for "equity" types
that track a market value alongside an outstanding loan and contribute only the
difference (value minus loan), e.g. property and vehicles. The taxonomy is a
fixed built-in set; users do not create their own types.
"""
from __future__ import annotations

import enum

from app.extensions import db


class Classification(enum.Enum):
    """Whether an account adds to or subtracts from net worth."""

    asset = "asset"
    liability = "liability"


class AccountType(db.Model):
    __tablename__ = "account_type"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    classification = db.Column(db.Enum(Classification), nullable=False)
    tracks_loan = db.Column(db.Boolean, nullable=False, default=False)
    is_builtin = db.Column(db.Boolean, nullable=False, default=False)

    accounts = db.relationship("Account", back_populates="account_type")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AccountType {self.name} ({self.classification.value})>"
