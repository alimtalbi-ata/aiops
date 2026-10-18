#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
: "${POSTGRES_CONTAINER:=aiops-postgres}"
: "${POSTGRES_USER:=aiops}"
: "${POSTGRES_DB:=aiops}"

exec_sql(){ docker exec -i "$POSTGRES_CONTAINER" psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" "$@"; }

# The clean-slate bootstrap has already executed 000..012 through PostgreSQL's
# docker-entrypoint-initdb.d. On an existing V7.x database, establish that
# known baseline once, after verifying the canonical schema exists.
exec_sql <<'SQL' >/dev/null
create schema if not exists aiops;
create table if not exists aiops.schema_migrations(version text primary key, applied_at timestamptz not null default now());
SQL

if exec_sql -Atqc "select 1 from aiops.runs limit 1" >/dev/null 2>&1; then
  for f in db/migrations/{000_n8n,001_schema,002_integrity,003_seed_twin,004_operational_model,005_seed_acme,006_execution_receipts,007_runtime_hardening,008_event_idempotency,009_twin_run_overrides,010_operational_integrity,011_idempotency_indexes,012_outbox_leases}.sql; do
    v="$(basename "$f")"
    exec_sql -c "insert into aiops.schema_migrations(version) values ('$v') on conflict do nothing;" >/dev/null
  done
fi

for f in db/migrations/*.sql; do
  v="$(basename "$f")"
  applied="$(exec_sql -Atqc "select count(*) from aiops.schema_migrations where version='$v'")"
  if [ "$applied" = "1" ]; then continue; fi
  exec_sql < "$f" >/dev/null
  exec_sql -c "insert into aiops.schema_migrations(version) values ('$v') on conflict do nothing;" >/dev/null
  echo "APPLIED|$v"
done
echo MIGRATIONS=PASS
