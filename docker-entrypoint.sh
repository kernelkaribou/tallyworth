#!/bin/sh
set -e

# When started as root, apply PUID/PGID/TZ, take ownership of the data volume,
# then drop to the unprivileged app user. This lets a plain bind mount
# (./tallyworth-data:/data) work regardless of host ownership.
if [ "$(id -u)" = "0" ]; then
  PUID="${PUID:-1000}"
  PGID="${PGID:-1000}"

  # Never run as root: reject ids that aren't positive integers.
  if ! echo "$PUID" | grep -qE '^[1-9][0-9]*$' || ! echo "$PGID" | grep -qE '^[1-9][0-9]*$'; then
    echo "PUID/PGID must be positive integers (got PUID=$PUID PGID=$PGID)" >&2
    exit 1
  fi

  # Match the app user/group to the requested ids so files on the bind mount
  # are owned by the host user you choose.
  groupmod -o -g "$PGID" app
  usermod -o -u "$PUID" app

  # Timezone: link the requested zone if tzdata has it.
  if [ -n "$TZ" ] && [ -f "/usr/share/zoneinfo/$TZ" ]; then
    ln -snf "/usr/share/zoneinfo/$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
  fi

  chown -R app:app /data
  exec gosu app "$0" "$@"
fi

# Apply database migrations and seed built-in account types before serving.
flask db upgrade
flask seed-types

exec "$@"
