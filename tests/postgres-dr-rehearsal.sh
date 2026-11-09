#!/usr/bin/env bash
# Disposable PostgreSQL DR drill. No live services or external hosts.
set -Eeuo pipefail
: "${PGPASSWORD:?PGPASSWORD_required}"
HOST="${DR_POSTGRES_HOST:-127.0.0.1}"
PORT="${DR_POSTGRES_PORT:-5432}"
USER="${DR_POSTGRES_USER:-aiops}"
SOURCE="${DR_SOURCE_DB:-aiops}"
TARGET="aiops_dr_rehearsal"
[[ "$HOST" == 127.0.0.1 || "$HOST" == localhost ]] || { echo 'FAIL|dr_must_run_on_loopback'; exit 2; }
[[ "$SOURCE" == aiops && "$TARGET" != "$SOURCE" ]] || { echo 'FAIL|dr_unsafe_database_identity'; exit 2; }
export PGHOST="$HOST" PGPORT="$PORT" PGUSER="$USER"
# Use one explicitly selected PostgreSQL 16 toolchain. Never rewrite dump SQL.
DR_POSTGRES_BINDIR="${DR_POSTGRES_BINDIR:-$(dirname "$(command -v pg_dump)")}"
for tool in pg_dump pg_restore psql; do
  tool_path="$DR_POSTGRES_BINDIR/$tool"
  [[ -x "$tool_path" ]] || { echo "FAIL|dr_missing_client|$tool_path"; exit 2; }
  tool_version="$("$tool_path" --version)"
  echo "DR_CLIENT|tool=$tool|path=$(readlink -f "$tool_path")|version=$tool_version"
  [[ "$tool_version" =~ \(PostgreSQL\)\ 16\. ]] || { echo "FAIL|dr_client_major_must_be_16|$tool"; exit 2; }
done
export PATH="$DR_POSTGRES_BINDIR:$PATH"
server_version="$(psql -d "$SOURCE" -At -v ON_ERROR_STOP=1 -c 'SHOW server_version')"
server_version_num="$(psql -d "$SOURCE" -At -v ON_ERROR_STOP=1 -c 'SHOW server_version_num')"
echo "DR_SERVER|host=$HOST|port=$PORT|version=$server_version|version_num=$server_version_num"
[[ "$server_version_num" =~ ^16[0-9]{4}$ ]] || { echo 'FAIL|dr_server_major_must_be_16'; exit 2; }
# Ask this disposable server for its executable path; not a host filesystem probe.
psql -d "$SOURCE" -At -v ON_ERROR_STOP=1 -c "SELECT name, setting FROM pg_config WHERE name IN ('BINDIR', 'VERSION') ORDER BY name"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/reports"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if [[ "$(psql -d postgres -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM pg_database WHERE datname='$TARGET'")" != 0 ]]; then
  echo 'FAIL|existing_dr_target'; exit 2
fi
pg_dump -d "$SOURCE" --format=custom -f "$TMP/source.dump"
pg_restore --list "$TMP/source.dump" > "$TMP/toc"
test -s "$TMP/toc"
# Deliberate corruption must NOT be classified as restorable.
printf 'invalid backup corruption fixture\n' > "$TMP/corrupt.dump"
if pg_restore --list "$TMP/corrupt.dump" >/dev/null 2>&1; then
  echo 'FAIL|corrupt_archive_accepted'; exit 3
fi
psql -d postgres -v ON_ERROR_STOP=1 -c "CREATE DATABASE $TARGET"
# Scope cleanup to the database created by this run.
cleanup_db() {
  psql -d postgres -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS $TARGET" >/dev/null || true
}
trap 'cleanup_db; rm -rf "$TMP"' EXIT
pg_restore -d "$TARGET" --no-owner --exit-on-error --single-transaction "$TMP/source.dump"
QUERY="SELECT table_name FROM information_schema.tables WHERE table_schema='aiops' AND table_type='BASE TABLE' ORDER BY table_name"
mapfile -t tables < <(psql -d "$SOURCE" -At -v ON_ERROR_STOP=1 -c "$QUERY")
[[ "${#tables[@]}" -gt 0 ]] || { echo 'FAIL|empty_source_schema'; exit 3; }
for table in "${tables[@]}"; do
  [[ "$table" =~ ^[a-zA-Z_][a-zA-Z_0-9]*$ ]] || { echo 'FAIL|unsafe_table_name'; exit 3; }
  # Deterministic hash of canonical row representations, independent of insertion order.
  SQL="SELECT count(*)::text || ':' || md5(coalesce(string_agg(md5(row_to_json(t)::text), '' ORDER BY md5(row_to_json(t)::text)),'')) FROM aiops.\"$table\" t"
  lhs="$(psql -d "$SOURCE" -At -v ON_ERROR_STOP=1 -c "$SQL")"
  rhs="$(psql -d "$TARGET" -At -v ON_ERROR_STOP=1 -c "$SQL")"
  [[ "$lhs" == "$rhs" ]] || { echo "FAIL|dr_data_mismatch|$table"; exit 4; }
done
SOURCE_COUNT="${#tables[@]}"
TARGET_COUNT="$(psql -d "$TARGET" -At -v ON_ERROR_STOP=1 -c "SELECT count(*) FROM information_schema.tables WHERE table_schema='aiops' AND table_type='BASE TABLE'")"
[[ "$SOURCE_COUNT" == "$TARGET_COUNT" ]] || { echo 'FAIL|dr_table_count_mismatch'; exit 4; }
python3 - "$ROOT/reports/postgres-dr-rehearsal.json" "$SOURCE_COUNT" <<'PY'
import json,sys,datetime
from pathlib import Path
p=Path(sys.argv[1])
data={"result":"PASS","kind":"disposable_postgres_logical_restore",
      "table_count":int(sys.argv[2]),"table_row_hashes":"MATCH",
      "corruption_negative_control":"PASS","target":"ephemeral_ci_database",
      "live_system_touched":False,"temporal_mariadb_volumes":"NOT_QUALIFIED",
      "timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat()}
p.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
PY
echo "POSTGRES_DR_REHEARSAL=PASS|tables=$SOURCE_COUNT|scope=disposable_ci_only"
