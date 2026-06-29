# Copilot instructions: Tallyworth

Maintain this file as the durable development context for the project.

## What Tallyworth is

A simple personal NET WORTH tracker. It is a "pretty Excel sheet" as a webpage, NOT a budgeting
or transactions tool. Accounts hold a running time series of values (latest value is current).
There is a light income-vs-expense green/red cashflow indicator, asset/equity tracking, a total
net worth figure, charts, and a per-timeframe net worth change summary.

## Core product decisions

- Single-user, self-hosted. No authentication in alpha.
- Single currency. Display symbol configured via `CURRENCY_SYMBOL` (default `$`).
- `SECRET_KEY`: optional. When unset, `_ensure_secret_key` in `app/__init__.py` generates a strong
  key and persists it at `DATA_DIR/secret_key` (auto-created), so a fresh deploy needs no config;
  set the env var to override. SQLite DB and secret both live in `DATA_DIR` (`/data` in Docker).
- Security headers: `_register_security_headers` in `app/__init__.py` adds `X-Content-Type-Options`,
  `X-Frame-Options`, `Referrer-Policy`, and a CSP. Inline `<script>` blocks (theme bootstrap, theme
  toggle, account-form loan reveal) carry a per-request `nonce="{{ csp_nonce }}"`; add the nonce to
  any new inline script or it will be blocked.
- CSRF: all state-changing POST forms are protected by Flask-WTF `CSRFProtect` (initialised in
  `app/__init__.py`). Every form includes `{{ csrf_field() }}` (macro in `_macros.html`). Tests
  disable it via `TestConfig.WTF_CSRF_ENABLED = False`; `tests/test_csrf.py` covers enforcement.
- Money values are stored as integer cents and parsed via `app/money.py` (rejects empty,
  non-numeric, scientific notation, inf/nan, >2 decimals, and absurdly large values). Liability
  account values must be non-negative (amount owed); asset accounts may go negative (overdraft).
- Money is stored as INTEGER CENTS. Never use floats for money.
- Net worth = assets minus liabilities (a gross balance sheet). Liability accounts add to
  liabilities; ordinary assets add to assets; loan-tracking assets (Property/Vehicle) add their
  full market value to assets AND their loan balance to liabilities, so the loan is never masked
  and an underwater asset drives net worth negative without a negative asset figure. The net figure
  equals each asset's equity (value minus loan). `display_value_map` returns the gross market value
  per account; `loan_balance_map` returns the loan portion for loan-tracking accounts so the UI can
  show it as a liability sub-line. Income/expenses are a SEPARATE monthly cashflow indicator
  and do NOT feed the net worth figure.
- Accounts use a unified `account` table with an `account_type`. Account types have a
  `classification` (asset or liability) and a `tracks_loan` flag (equity types like
  Property/Vehicle: net worth gets value minus loan). The taxonomy is a fixed built-in set
  seeded by `flask seed-types` (which also migrates older renamed/removed built-ins);
  users do NOT create custom types. An account's type is locked once it has recorded values.
- Net worth over time is computed by forward-filling each account's last known value across all
  change dates. Before an account's first value it is absent (not zero). Archived accounts keep
  their historical contribution but are excluded from the current figure.
- Projection: linear least-squares over an account's history, requires >= 3 points, rendered as a
  dashed "trend estimate" (never a forecast).

## Tech stack

- Python 3.13, Flask + Jinja2, HTMX (vendored), Tailwind CSS v4, Chart.js (vendored).
- SQLite via Flask-SQLAlchemy + Flask-Migrate (Alembic). DB lives in `data/`.
- gunicorn in the container. pytest for tests.
- Docker is the preferred runtime and test environment. Image published to
  `ghcr.io/kernelkaribou/tallyworth`.

## Project layout

- `app/` - application package (factory in `__init__.py`, `config.py`, `extensions.py`).
- `app/blueprints/` - Flask blueprints. `app/models/` - SQLAlchemy models.
- `app/templates/` - Jinja templates. `app/static/` - CSS (Tailwind) and vendored JS.
- `migrations/` - Alembic migrations. `tests/` - pytest suite.
- `wsgi.py` - gunicorn entrypoint. `VERSION` - current version string.

## Common commands

- Install (dev): `pip install -r requirements-dev.txt`
- Run tests: `pytest`
- Build CSS: `npm install && npm run build:css` (watch: `npm run watch:css`)
- Run locally: `FLASK_APP=wsgi.py flask run` (after building CSS)
- Migrations: `FLASK_APP=wsgi.py flask db migrate -m "msg"` then `flask db upgrade`
- Docker: `docker compose up -d` (published image); container runs migrations + seed and supports `PUID`/`PGID`/`TZ`

## Workflow rules (see tmp/DEV.md)

- Work on feature branches off `dev`; the agent pushes feature branches and to `dev`.
- Only the owner opens `dev` -> `main` PRs and creates GitHub releases.
- Bump `VERSION` before a `main` merge, when the owner requests it.
- Push to `dev` builds a `dev`-tagged GHCR image; push to `main` builds `latest`.
- Always diff `dev` vs `main` before starting a new task.
- Break disparate tasks into individual approaches; do not lump them together.
- Run a full audit (security, performance, best practices, reusability + rubber duck) after each
  feature is implemented or a full feature is removed.
- Backwards-compatibility code paths are only honored once the app is released (not in alpha).
- README is public, non-technical, and contains NO EMOJIS.
- Cover code with unit tests as a release approaches.
