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
sql() {
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$1" "${@:2}"
}
# The dedicated Temporal Postgres volume is initialized from scratch in this
# disposable stack. The official admin-tools CLI creates both databases and
# applies the versioned schemas before the server is allowed to start.
for database in temporal temporal_visibility; do
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" create
done
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal update-schema -d /etc/temporal/schema/postgresql/v12/temporal/versioned
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal_visibility setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal_visibility update-schema -d /etc/temporal/schema/postgresql/v12/visibility/versioned
echo 'TEMPORAL_SCHEMA_SETUP=PASS'
