#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -f .env ]] || { echo 'FAIL|missing_env|run_deploy_init_env_first'; exit 2; }
read_env() { grep -m1 "^$1=" .env | cut -d= -f2-; }
DB_USER="$(read_env POSTGRES_USER)"; DB_NAME="$(read_env POSTGRES_DB)"
[[ -n "$DB_USER" ]] || DB_USER=aiops
[[ -n "$DB_NAME" ]] || DB_NAME=aiops
psqlc() { docker compose --env-file .env exec -T aiops2-postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" "$@"; }
docker compose --env-file .env exec -T aiops2-postgres pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null
# Fail closed rather than guessing how to upgrade a partial or unknown legacy schema.
BASELINE_OK="$(psqlc -Atqc "select (to_regclass('aiops.runs') is not null and to_regclass('aiops.run_events') is not null and to_regclass('aiops.evidence') is not null and to_regclass('aiops.gates') is not null and to_regclass('aiops.twin_facts') is not null and to_regclass('aiops.incidents') is not null and to_regclass('aiops.run_checkpoints') is not null and exists(select 1 from information_schema.columns where table_schema='aiops' and table_name='run_events' and column_name='event_key'))::text")"
[[ "$BASELINE_OK" == true ]] || { echo 'FAIL|legacy_schema_incomplete|refusing_to_guess'; exit 3; }
psqlc -q -c "create table if not exists public.aiops_schema_migrations(version text primary key, checksum text not null, applied_at timestamptz not null default now(), execution_mode text not null check(execution_mode in ('BOOTSTRAP_BASELINE','APPLIED')))"
# Adopt the verified initdb baseline only after the schema signature above succeeds.
for file in db/migrations/00[0-8]_*.sql; do
  [[ -f "$file" ]] || continue
  version="$(basename "$file")"; checksum="$(sha256sum "$file" | awk '{print $1}')"
  existing="$(psqlc -Atqc "select checksum from public.aiops_schema_migrations where version='$version'")"
  if [[ -z "$existing" ]]; then
    psqlc -q -c "insert into public.aiops_schema_migrations(version,checksum,execution_mode) values ('$version','$checksum','BOOTSTRAP_BASELINE') on conflict(version) do nothing"
  elif [[ "$existing" != "$checksum" ]]; then
    echo "FAIL|migration_checksum_changed|$version"; exit 4
  fi
done
# Every post-bootstrap migration runs transactionally and is immutable once applied.
for file in db/migrations/00[9]_*.sql db/migrations/0[1-9][0-9]_*.sql db/migrations/[1-9][0-9][0-9]_*.sql; do
  [[ -f "$file" ]] || continue
  version="$(basename "$file")"; checksum="$(sha256sum "$file" | awk '{print $1}')"
  existing="$(psqlc -Atqc "select checksum from public.aiops_schema_migrations where version='$version'")"
  if [[ -n "$existing" ]]; then
    [[ "$existing" == "$checksum" ]] || { echo "FAIL|migration_checksum_changed|$version"; exit 4; }
    echo "MIGRATION=SKIP|$version"; continue
  fi
  {
    printf 'BEGIN;\n'
    cat "$file"
    printf "\ninsert into public.aiops_schema_migrations(version,checksum,execution_mode) values ('%s','%s','APPLIED');\nCOMMIT;\n" "$version" "$checksum"
  } | psqlc -q
  echo "MIGRATION=APPLIED|$version"
done
echo 'MIGRATIONS=PASS'
