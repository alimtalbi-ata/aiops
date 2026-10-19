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
# Try the non-destructive forward upgrade first. If the database or schema
# version tables are absent, create/setup and then apply the versioned schema.
upgrade_schema() {
  database="$1"
  schema_dir="$2"
  if temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" update-schema -d "$schema_dir" >/dev/null 2>&1; then
    echo "TEMPORAL_SCHEMA_ALREADY_INITIALIZED|$database"
    return 0
  fi
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" create >/dev/null 2>&1 || true
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" setup-schema -v 0.0
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" update-schema -d "$schema_dir"
}
upgrade_schema temporal /etc/temporal/schema/postgresql/v12/temporal/versioned
upgrade_schema temporal_visibility /etc/temporal/schema/postgresql/v12/visibility/versioned
echo 'TEMPORAL_SCHEMA_SETUP=PASS'
