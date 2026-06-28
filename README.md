# Tallyworth

Tallyworth is a simple, self-hosted web app for tracking your personal net worth
over time. Think of it as a tidy spreadsheet that lives in your browser: you add
your accounts, update their values whenever you like, and Tallyworth shows you
where you stand and how things are trending.

It is intentionally small. Tallyworth is **not** a budgeting app, a transaction
tracker, or a financial planning tool. It does not connect to your bank. You are
in full control of the numbers you enter.

## What it does

- **Track accounts of any kind.** Add an account with a name and a value, such as
  a checking account, a savings account, a brokerage account, or anything else.
- **Keep a running value.** Each account holds a running history of values. When
  your checking balance changes, you record the new value; the latest value is
  the current one, and the history is kept for charts.
- **Separate assets from liabilities.** Mark account types as assets (things you
  own) or liabilities (things you owe). Liabilities subtract from your net worth.
- **Choose an account type.** Pick from a fixed set of built-in types
  (checking, savings, investments, retirement, property, vehicle, credit card,
  loan, and more). Each type defines how the account counts toward net worth.
- **Track equity on financed assets.** For things like a house or a car, record
  both the market value and the outstanding loan. Tallyworth counts the equity
  (value minus loan) toward your net worth.
- **See how you're trending.** Every account has its own value-over-time chart,
  and the dashboard shows your total net worth over time. Pick a timeframe
  (1M, 3M, 1Y, YTD, 3Y, 5Y, or lifetime) and Tallyworth summarizes how much your
  net worth went up or down over that period.
- **Note your monthly cash flow.** Record recurring monthly income and expenses
  to see whether your month is in the green or the red. This is informational
  only and does not affect your net worth.
- **Dark mode.** Toggle between light and dark themes from the top navigation;
  your choice is remembered in your browser.
- **Pick your currency.** Set your display currency once via an environment
  variable (see the configuration table below).

## Getting started

### Run with Docker (recommended)

The easiest way to run Tallyworth is with Docker Compose.

1. Copy the example environment file and set a strong secret key:

   ```sh
   cp .env.example .env
   # Generate a key with:
   python -c "import secrets; print(secrets.token_hex(32))"
   # then paste it into .env as SECRET_KEY=...
   ```

2. Start the app:

   ```sh
   docker compose up --build
   ```

3. Open <http://localhost:8000> in your browser.

Your data is stored in a SQLite database on the `tallyworth-data` Docker volume,
so it persists across restarts and upgrades. The container applies database
migrations and seeds the built-in account types automatically on startup.

### Configuration

Tallyworth is configured through environment variables:

| Variable              | Required | Default                         | Description                                               |
| --------------------- | -------- | ------------------------------- | --------------------------------------------------------- |
| `SECRET_KEY`          | Yes      | (insecure dev default)          | Random secret used to secure the app. Set a strong value. |
| `DEFAULT_CURRENCY`    | No       | `USD`                           | ISO currency code (USD, EUR, GBP, JPY, CNY, CAD, AUD, CHF, INR, KRW, BRL, MXN, SEK, NZD, ZAR). Sets the symbol shown next to amounts. Unknown codes fall back to USD. |
| `CURRENCY_SYMBOL`     | No       | (from `DEFAULT_CURRENCY`)       | Optional raw symbol override for a currency not in the list. Takes precedence over `DEFAULT_CURRENCY`. |
| `DATABASE_URL`        | No       | SQLite file in the data dir     | SQLAlchemy database URL, if you want a different store.    |
| `TALLYWORTH_DATA_DIR` | No       | `./data` (or `/data` in Docker) | Directory where the SQLite database is kept.              |

## Development

Tallyworth is a Flask application. To run it locally without Docker:

1. Create a virtual environment and install dependencies:

   ```sh
   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

2. Build the stylesheet (requires Node.js):

   ```sh
   npm install
   npm run build:css
   ```

3. Apply migrations, seed the built-in types, and run the app:

   ```sh
   export FLASK_APP=wsgi.py
   export SECRET_KEY=dev-only-not-for-production
   flask db upgrade
   flask seed-types
   flask run
   ```

   Then open <http://localhost:5000>.

### Common tasks

- **Run the tests:** `pytest`
- **Rebuild CSS after template changes:** `npm run build:css` (or `npm run watch:css`)
- **Create a migration after a model change:** `flask db migrate -m "describe change"` then `flask db upgrade`

## Tech stack

Flask, SQLAlchemy, and Flask-Migrate (Alembic) on SQLite, with server-rendered
Jinja templates, Tailwind CSS, a touch of HTMX, and Chart.js for the charts.
Forms are CSRF-protected with Flask-WTF. Served by gunicorn in the published
Docker image.

## Status

Tallyworth is in early alpha (see `VERSION`). Features and data structures may
change. There is no built-in authentication yet, so run it on a trusted network
or behind your own access controls.

## Disclaimer

AI was used heavily to create this project.

Tallyworth is provided as-is for personal tracking. It is not financial advice.
Any figures and summaries it shows are based solely on the numbers you enter.
Always keep your own records and verify important figures yourself.
