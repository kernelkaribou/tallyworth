"""Account type taxonomy.

An account type carries the financial classification that drives net worth maths
(assets are positive, liabilities are negative) and a flag for types that track a
loan/equity workflow (e.g. real estate, vehicles).
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

    @property
    def is_asset(self) -> bool:
        return self.classification == Classification.asset

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<AccountType {self.name} ({self.classification.value})>"
