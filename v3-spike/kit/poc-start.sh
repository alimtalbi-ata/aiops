#!/usr/bin/env bash
set -euo pipefail
umask 077
export V3_ROOT="${V3_ROOT:-/srv/aiops-v3}"
[[ "$V3_ROOT" = /* && "$V3_ROOT" != / ]] || { echo "Absolute dedicated root required" >&2; exit 1; }
[[ "$(id -u)" != 0 ]] || { echo "Rootless user required" >&2; exit 1; }
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$here/rootless_preflight.py" "$V3_ROOT" --source-daemon-only
mkdir -p "$V3_ROOT"
[[ "$(realpath "$V3_ROOT")" = "$V3_ROOT" && -O "$V3_ROOT" ]] || exit 1
[[ ! -L "$V3_ROOT/data" && ! -L "$V3_ROOT/data/postgres" ]] || exit 1
mkdir -p "$V3_ROOT/data/postgres"
[[ "$(realpath "$V3_ROOT/data/postgres")" = "$V3_ROOT/data/postgres" ]] || exit 1
[[ ! -L "$V3_ROOT/data/temporal-postgres" ]] || exit 1
mkdir -p "$V3_ROOT/data/temporal-postgres"
[[ "$(realpath "$V3_ROOT/data/temporal-postgres")" = "$V3_ROOT/data/temporal-postgres" ]] || exit 1
envfile="$V3_ROOT/poc.env"
if [[ ! -e "$envfile" ]]; then
  (set -o noclobber; printf 'V3_DB_PASSWORD=%s\nV3_LAB_TOKEN=%s\n' "$(openssl rand -hex 24)" "$(openssl rand -hex 32)" > "$envfile")
fi
[[ -f "$envfile" && ! -L "$envfile" && -O "$envfile" ]] || exit 1
chmod 600 "$envfile"
unset V3_DB_PASSWORD V3_LAB_TOKEN
compose=(docker compose --project-name "aiops-v3-poc-$(printf %s "$V3_ROOT" | sha256sum | cut -c1-12)" --env-file "$envfile" -f "$here/compose.poc-source.yml")
"${compose[@]}" config --quiet
# PostgreSQL init scripts only run on an empty data directory.
# Apply the additive 008 migration before starting newer application services.
"${compose[@]}" up --wait --wait-timeout 120 postgres
schema_ready=$("${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U aiops -d aiops -Atc "select exists(select 1 from information_schema.columns where table_schema='aiops' and table_name='run_events' and column_name='event_key') and to_regclass('aiops.ux_run_events_event_key') is not null and to_regclass('aiops.execution_receipts') is not null")
if [[ "$schema_ready" != t ]]; then
  [[ ! -L "$V3_ROOT/backup" ]] || exit 1
  mkdir -p "$V3_ROOT/backup"
  [[ "$(realpath "$V3_ROOT/backup")" = "$V3_ROOT/backup" && -O "$V3_ROOT/backup" ]] || exit 1
  backup=$(mktemp "$V3_ROOT/backup/pre-poc-schema.XXXXXX")
  if ! "${compose[@]}" exec -T postgres pg_dump -U aiops -Fc aiops > "$backup" || [[ ! -s "$backup" ]]; then
    rm -f "$backup"
    echo "Pre-upgrade backup failed; refusing migration" >&2
    exit 1
  fi
  echo "Pre-upgrade backup: $backup"
fi
"${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 --single-transaction -U aiops -d aiops < "$here/../../db/migrations/008_event_idempotency.sql"
"${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 --single-transaction -U aiops -d aiops < "$here/poc-execution-receipts.sql"
# Retry only a confirmed port binding collision, never delete persistent data.
log=$(mktemp "$V3_ROOT/.compose-start.XXXXXX")
trap 'rm -f "$log"' EXIT
for attempt in 1 2 3; do
  if "${compose[@]}" up --build --wait --wait-timeout 300 >"$log" 2>&1; then
    cat "$log"
    break
  else
    status=$?
  fi
  cat "$log" >&2
  if [[ "$attempt" == 3 ]] || ! grep -Eqi 'address already in use|port is already allocated' "$log"; then
    exit "$status"
  fi
  echo "Port collision; recreating only this POC project's service containers" >&2
  "${compose[@]}" rm -sf core twin evidence policy
  sleep "$attempt"
done
rm -f "$log"
trap - EXIT
"${compose[@]}" ps
"${compose[@]}" exec -T postgres psql -v ON_ERROR_STOP=1 -U aiops -d aiops < "$here/poc-seed.sql"
endpoint=$("${compose[@]}" port evidence 812)
[[ "$endpoint" =~ ^127\.0\.0\.1:[0-9]+$ ]] || exit 1
[[ "${endpoint##*:}" != 7770 && "${endpoint##*:}" != 7777 && "${endpoint##*:}" != 7790 ]] || exit 1
for sample in baseline:40 incident:160; do
  phase="${sample%:*}"; value="${sample#*:}"
  curl --fail --silent --show-error --max-time 10 -H 'Content-Type: application/json' \
    -d "{\"source\":\"poc-kit-$phase\",\"claim\":\"synthetic latency sample\",\"confidence\":0.5,\"provenance\":{\"run_id\":\"RUN-CI-CONTEXT\",\"synthetic\":true},\"payload\":{\"metric\":\"latency_ms\",\"phase\":\"$phase\",\"value\":$value}}" \
    "http://$endpoint/api/evidence"
  printf '\n'
done
