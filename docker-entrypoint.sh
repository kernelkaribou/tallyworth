#!/bin/sh
set -e

# Apply database migrations and seed built-in account types before serving.
flask db upgrade
flask seed-types

exec "$@"
