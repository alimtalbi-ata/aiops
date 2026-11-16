#!/bin/sh
set -eu
: "${POSTGRES_SEEDS:?POSTGRES_SEEDS is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PWD:?POSTGRES_PWD is required}"
DB_PORT="${DB_PORT:-5432}"
export SQL_PASSWORD="${POSTGRES_PWD}"
waited=0
until nc -z -w 2 "$POSTGRES_SEEDS" "$DB_PORT"; do
  waited=$((waited + 1))
  if [ "$waited" -ge 60 ]; then echo "FAIL|temporal_postgres_unavailable"; exit 1; fi
  sleep 2
done
ensure_database() {
  database="$1"
  if output="$(temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" create 2>&1)"; then
    echo "TEMPORAL_DATABASE_CREATED=$database"
  else
    printf '%s\n' "$output"
    printf '%s\n' "$output" | grep -Eqi 'already exists|duplicate database' || {
      echo "FAIL|temporal_database_create|$database"; exit 1;
    }
    echo "TEMPORAL_DATABASE_EXISTS=$database"
  fi
}
setup_database_schema() {
  database="$1"
  schema_path="$2"
  ensure_database "$database"
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" setup-schema -v 0.0
  temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db "$database" update-schema -d "$schema_path"
  echo "TEMPORAL_SCHEMA_READY=$database"
}
setup_database_schema temporal /etc/temporal/schema/postgresql/v12/temporal/versioned
setup_database_schema temporal_visibility /etc/temporal/schema/postgresql/v12/visibility/versioned
echo "TEMPORAL_SCHEMA_SETUP=PASS"
