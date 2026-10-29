#!/usr/bin/env bash
# Isolated MariaDB disaster-recovery rehearsal; CI only, never real hosts.
set -Eeuo pipefail
[[ "${AIOPS_CI_DR:-}" == "YES" ]] || { echo "FAIL|requires_explicit_ci_dr"; exit 2; }
command -v docker >/dev/null
TMP="$(mktemp -d)"
NAME="aiops-dr-mariadb-${GITHUB_RUN_ID:-local}-${GITHUB_RUN_ATTEMPT:-1}"
[[ "$NAME" =~ ^[A-Za-z0-9_-]+$ ]] || exit 2
PASSWORD="ci-disposable-only-password"
IMAGE="mariadb:11.4"
cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  rm -rf "$TMP"
}
trap cleanup EXIT
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FAIL|refusing_existing_container"; exit 2
fi
docker run -d --name "$NAME" --network none --label aiops.dr.disposable=true \
  -e MARIADB_ROOT_PASSWORD="$PASSWORD" "$IMAGE" >/dev/null
db() { docker exec -e MYSQL_PWD="$PASSWORD" "$NAME" mariadb -uroot "$@"; }
dump() { docker exec -e MYSQL_PWD="$PASSWORD" "$NAME" mariadb-dump -uroot "$@"; }
ready=0
for i in $(seq 1 90); do
  if db -N -e 'SELECT 1' >/dev/null 2>&1; then ready=1; break; fi
  sleep 2
done
[[ "$ready" == 1 ]] || { echo 'FAIL|mariadb_not_ready'; exit 3; }
db -e "CREATE DATABASE aiops_dr_source; CREATE TABLE aiops_dr_source.recovery_fixture(id INT PRIMARY KEY, detail VARCHAR(255) NOT NULL); INSERT INTO aiops_dr_source.recovery_fixture VALUES(1,'restorable'),(2,'idempotent');"
SOURCE_HASH="$(db -N -e "SELECT SHA2(GROUP_CONCAT(CONCAT(id,':',detail) ORDER BY id SEPARATOR '|'),256) FROM aiops_dr_source.recovery_fixture")"
dump aiops_dr_source > "$TMP/source.sql"
[[ -s "$TMP/source.sql" ]] || { echo 'FAIL|dump_empty'; exit 3; }
# Restore into a distinct database to avoid damaging even the synthetic source.
db -e 'CREATE DATABASE aiops_dr_restored'
sed 's/USE `aiops_dr_source`;/USE `aiops_dr_restored`;/' "$TMP/source.sql" > "$TMP/restored.sql"
# mariadb-dump with a single named database normally omits CREATE/USE; direct stdin selects target DB.
docker exec -i -e MYSQL_PWD="$PASSWORD" "$NAME" mariadb -uroot aiops_dr_restored < "$TMP/source.sql"
RESTORED_HASH="$(db -N -e "SELECT SHA2(GROUP_CONCAT(CONCAT(id,':',detail) ORDER BY id SEPARATOR '|'),256) FROM aiops_dr_restored.recovery_fixture")"
[[ -n "$SOURCE_HASH" && "$SOURCE_HASH" == "$RESTORED_HASH" ]] || { echo 'FAIL|restore_integrity_mismatch'; exit 4; }
# Corrupt SQL must trigger a nonzero import error (fail closed).
printf 'THIS IS NOT SQL;\n' > "$TMP/corrupt.sql"
if docker exec -i -e MYSQL_PWD="$PASSWORD" "$NAME" mariadb -uroot aiops_dr_restored < "$TMP/corrupt.sql" >/dev/null 2>&1; then
  echo 'FAIL|corrupt_sql_accepted'; exit 4
fi
mkdir -p reports
python3 - <<'PY'
import json,datetime,pathlib
result={'result':'PASS','kind':'disposable_mariadb_logical_restore',
 'source_records':2,'restored_records':2,'row_integrity':'MATCH',
 'corruption_negative_control':'PASS','network':'none','live_system_touched':False,
 'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
pathlib.Path('reports/mariadb-dr-rehearsal.json').write_text(json.dumps(result,indent=2)+'\n')
PY
echo 'MARIADB_DR_REHEARSAL=PASS|scope=disposable_ci_only'
