"""Seeding of the built-in account type taxonomy.

The built-in types are idempotently inserted (by name). Users may add their own
custom types at runtime; those are never touched by seeding.
"""
from __future__ import annotations

import click
from flask import Flask, current_app
from flask.cli import with_appcontext

from app.extensions import db
from app.models.account_type import AccountType, Classification

ASSET = Classification.asset
LIABILITY = Classification.liability

# (name, classification, tracks_loan)
BUILTIN_ACCOUNT_TYPES: tuple[tuple[str, Classification, bool], ...] = (
    ("Checking", ASSET, False),
    ("Savings", ASSET, False),
    ("Cash", ASSET, False),
    ("CD", ASSET, False),
    ("Brokerage / Stocks", ASSET, False),
    ("Retirement (401k/IRA)", ASSET, False),
    ("Real Estate", ASSET, True),
    ("Vehicle", ASSET, True),
    ("Other Asset", ASSET, False),
    ("Credit Card", LIABILITY, False),
    ("Loan", LIABILITY, False),
    ("Mortgage", LIABILITY, False),
    ("Other Liability", LIABILITY, False),
)


def seed_account_types() -> int:
    """Insert any missing built-in account types. Returns the number added.

    Matching is case-insensitive so a built-in is never duplicated by case. If a
    user-created (custom) type already occupies a built-in name, it is left as-is
    and a warning is logged rather than silently shadowing the built-in.
    """
    existing = {
        name.lower(): is_builtin
        for name, is_builtin in db.session.query(
            AccountType.name, AccountType.is_builtin
        ).all()
    }
    added = 0
    for name, classification, tracks_loan in BUILTIN_ACCOUNT_TYPES:
        key = name.lower()
        if key in existing:
            if not existing[key]:
                current_app.logger.warning(
                    "Built-in account type '%s' is shadowed by an existing custom "
                    "type; leaving the custom type in place.",
                    name,
                )
            continue
        db.session.add(
            AccountType(
                name=name,
                classification=classification,
                tracks_loan=tracks_loan,
                is_builtin=True,
            )
        )
        added += 1
    if added:
        db.session.commit()
    return added


def register_seed_cli(app: Flask) -> None:
    app.cli.add_command(seed_types_command)


@click.command("seed-types")
@with_appcontext
def seed_types_command() -> None:
    """Seed the built-in account types."""
    added = seed_account_types()
    click.echo(f"Seeded {added} built-in account type(s).")
