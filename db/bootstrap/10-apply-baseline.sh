#!/usr/bin/env bash
# PostgreSQL entrypoint initialization: apply only the immutable baseline 000-008.
# Post-baseline migrations are journaled and applied by deploy/migrate.sh after
# the database becomes healthy. Each file is executed in its own psql process so
# bootstrap operations such as CREATE DATABASE are not wrapped in a transaction.
set -Eeuo pipefail
MIGRATION_DIR=/opt/aiops/migrations
for migration in "$MIGRATION_DIR"/00[0-8]_*.sql; do
    [[ -f "$migration" ]] || continue
    echo "AIOPS_BASELINE_APPLY=$(basename "$migration")"
    psql --set ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --file "$migration"
done
echo "AIOPS_BASELINE=PASS"
