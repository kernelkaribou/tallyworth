"""Seeding of the built-in account type taxonomy.

The built-in types are idempotently inserted (by name) and are the only types
available; account types are a fixed taxonomy (no user-created types). Renames
and removals from earlier revisions are migrated in place by ``seed-types``.
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
#
# "tracks_loan" means the type records a market value AND an outstanding loan,
# and contributes its *equity* (value minus loan) to net worth. These are
# surfaced to users as "(Equity)" types.
BUILTIN_ACCOUNT_TYPES: tuple[tuple[str, Classification, bool], ...] = (
    ("Checking", ASSET, False),
    ("Savings", ASSET, False),
    ("Cash", ASSET, False),
    ("Investments", ASSET, False),
    ("Retirement", ASSET, False),
    ("Property (Equity)", ASSET, True),
    ("Vehicle (Equity)", ASSET, True),
    ("Other Asset", ASSET, False),
    ("Other Asset – financed (Equity)", ASSET, True),
    ("Credit Card", LIABILITY, False),
    ("Loan", LIABILITY, False),
    ("Other Liability", LIABILITY, False),
)

# Existing built-in types renamed by this revision. Applied (by old name) to
# built-in rows so on-disk databases migrate in place rather than ending up with
# duplicate old/new types.
RENAMED_BUILTINS: dict[str, str] = {
    "Brokerage / Stocks": "Investments",
    "Retirement (401k/IRA)": "Retirement",
    "Real Estate": "Property (Equity)",
    "Vehicle": "Vehicle (Equity)",
}

# Built-in types removed by this revision. Dropped only when no account uses
# them; an in-use retired type is left untouched so history is never orphaned.
RETIRED_BUILTINS: tuple[str, ...] = ("CD", "Mortgage")


def _migrate_builtin_names() -> None:
    """Rename/retire built-in types from earlier revisions in place."""
    by_name = {t.name: t for t in AccountType.query.all()}
    for old, new in RENAMED_BUILTINS.items():
        existing = by_name.get(old)
        if existing is None or not existing.is_builtin:
            continue
        if new in by_name:
            continue  # target already present; leave the stale row alone
        existing.name = new
        by_name[new] = existing
        del by_name[old]
    for name in RETIRED_BUILTINS:
        existing = by_name.get(name)
        if existing is None or not existing.is_builtin:
            continue
        if existing.accounts:
            continue  # still in use; keep it so history stays valid
        db.session.delete(existing)
        del by_name[name]


def seed_account_types() -> int:
    """Insert any missing built-in account types. Returns the number added.

    Matching is case-insensitive so a built-in is never duplicated by case. If a
    user-created (custom) type already occupies a built-in name, it is left as-is
    and a warning is logged rather than silently shadowing the built-in.
    """
    _migrate_builtin_names()
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
    if added or db.session.dirty or db.session.deleted:
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
