#!/bin/sh
set -eu
: "${POSTGRES_SEEDS:?POSTGRES_SEEDS required}"
: "${POSTGRES_USER:?POSTGRES_USER required}"
: "${POSTGRES_PWD:?POSTGRES_PWD required}"
DB_PORT="${DB_PORT:-5432}"
echo "TEMPORAL_SCHEMA|WAIT|$POSTGRES_SEEDS:$DB_PORT"
until nc -z "$POSTGRES_SEEDS" "$DB_PORT"; do sleep 1; done
echo "TEMPORAL_SCHEMA|SETUP"
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal create || true
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal update-schema -d /etc/temporal/schema/postgresql/v12/temporal/versioned
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal_visibility create || true
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal_visibility setup-schema -v 0.0
temporal-sql-tool --plugin postgres12 --ep "$POSTGRES_SEEDS" -u "$POSTGRES_USER" -p "$DB_PORT" --db temporal_visibility update-schema -d /etc/temporal/schema/postgresql/v12/visibility/versioned
echo "TEMPORAL_SCHEMA=PASS"
