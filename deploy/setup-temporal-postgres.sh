#!/bin/sh
set -eu
: "${POSTGRES_SEEDS:?POSTGRES_SEEDS is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PWD:?POSTGRES_PWD is required}"
DB_PORT="${DB_PORT:-5432}"
attempt=1
while ! nc -z -w 5 "$POSTGRES_SEEDS" "$DB_PORT"; do
  if [ "$attempt" -ge 60 ]; then
    echo "FAIL|temporal_postgres_unavailable"
    exit 1
  fi
  attempt=$((attempt + 1))
  sleep 2
done
# Create missing databases, initialize missing schemas, then apply forward
# migrations. Existing schema validation is used to avoid destructive re-setup.
for database in temporal temporal_visibility; do
  if ! temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" validate >/dev/null 2>&1; then
    temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" create >/dev/null 2>&1 || true
    temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" setup-schema -v 0.0
  fi
done
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal update-schema -d /etc/temporal/schema/postgresql/v12/temporal/versioned
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal_visibility update-schema -d /etc/temporal/schema/postgresql/v12/visibility/versioned
echo 'TEMPORAL_SCHEMA_SETUP=PASS'
