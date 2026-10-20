#!/usr/bin/env bash
# Offline, explicitly authorized restore to a verified isolated Compose project.
# Verify-only never starts/stops services, writes a database or modifies a volume.
set -Eeuo pipefail
umask 077
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE=RESTORE
if [[ "${1:-}" == "--verify-only" ]]; then
  MODE=VERIFY_ONLY
  shift
fi
BACKUP="${1:?Usage: bash deploy/restore.sh [--verify-only] <backup-directory>}"
[[ $# -eq 1 ]] || { echo 'FAIL|unexpected_restore_arguments'; exit 2; }
[[ -f .env ]] || { echo 'FAIL|missing_env'; exit 2; }
STACK_ID="$(sed -n 's/^AIOPS_STACK_ID=//p' .env | head -1)"
STACK_ID="${STACK_ID:-aiops2}"
[[ "$STACK_ID" =~ ^[a-z][a-z0-9-]{2,28}$ ]] || { echo 'FAIL|invalid_stack_id'; exit 2; }
BACKUP="$(cd "$BACKUP" && pwd)" || { echo 'FAIL|backup_directory_missing'; exit 2; }
python3 deploy/verify_backup.py "$BACKUP" "$STACK_ID"
if [[ "$MODE" == VERIFY_ONLY ]]; then
  echo "RESTORE_VERIFY_ONLY=PASS|stack_id=$STACK_ID|no_mutation=true"
  exit 0
fi

# Restoring a production-named stack is discouraged even with normal
# confirmations; require a separate and explicit override.
[[ "${CONFIRM_RESTORE:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_RESTORE=YES'; exit 3; }
[[ "${CONFIRM_TARGET_DATABASES:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_TARGET_DATABASES=YES'; exit 3; }
[[ "${CONFIRM_DATA_LOSS:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_DATA_LOSS=YES'; exit 3; }
[[ "${CONFIRM_STACK_ID:-}" == "$STACK_ID" ]] || { echo 'FAIL|CONFIRM_STACK_ID_mismatch'; exit 3; }
if [[ "$STACK_ID" == aiops2 && "${ALLOW_NONISOLATED_RESTORE:-}" != YES ]]; then
  echo 'FAIL|nonisolated_restore_requires_separate_authorization'
  exit 3
fi

PROJECT="$(docker compose --env-file .env config --format json | python3 -c 'import json,sys;print(json.load(sys.stdin)["name"])')"
[[ "$PROJECT" == "$STACK_ID" ]] || { echo 'FAIL|restore_compose_project_mismatch'; exit 4; }
DB_CONTAINER="$(docker compose --env-file .env ps -q aiops2-postgres)"
[[ -n "$DB_CONTAINER" ]] || { echo 'FAIL|restore_postgres_not_running'; exit 4; }
OWNER="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$DB_CONTAINER")"
[[ "$OWNER" == "$STACK_ID" ]] || { echo 'FAIL|restore_database_owned_by_other_stack'; exit 4; }
ARCHIVE_IMAGE="$(docker inspect --format '{{.Config.Image}}' "$DB_CONTAINER")"
for suffix in n8n-data glpi-data grafana-data prometheus-data; do
  volume="$STACK_ID-$suffix"
  [[ "$(docker volume inspect --format '{{.Name}}' "$volume" 2>/dev/null)" == "$volume" ]] || {
    echo "FAIL|restore_volume_not_owned_by_target|$volume"; exit 4;
  }
done

echo "RESTORE_START|stack_id=$STACK_ID|backup=$BACKUP"
# Stop every writer before restoring databases and volume files. Databases stay
# running to accept pg_restore/MariaDB imports; do not restart writers on failure.
docker compose --env-file .env stop \
  aiops2-worker aiops2-core aiops2-evidence aiops2-policy aiops2-intelligence \
  aiops2-copilot aiops2-twin aiops2-simulator aiops2-portal aiops2-temporal \
  aiops2-temporal-ui aiops2-n8n aiops2-glpi aiops2-grafana \
  aiops2-prometheus aiops2-alertmanager

docker compose --env-file .env exec -T aiops2-postgres sh -c \
  'pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < "$BACKUP/aiops.dump"
docker compose --env-file .env exec -T aiops2-postgres sh -c \
  'pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction -U "$POSTGRES_USER" -d n8n' \
  < "$BACKUP/n8n.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres \
  pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction \
  -U temporal -d temporal < "$BACKUP/temporal.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres \
  pg_restore --clean --if-exists --no-owner --exit-on-error --single-transaction \
  -U temporal -d temporal_visibility < "$BACKUP/temporal_visibility.dump"
docker compose --env-file .env exec -T aiops2-glpi-db sh -c \
  'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"' < "$BACKUP/glpi-mariadb.sql"

for suffix in n8n-data glpi-data grafana-data prometheus-data; do
  volume="$STACK_ID-$suffix"
  logical="aiops2-$suffix"
  # Backup archive integrity and path traversal were already checked by
  # verify_backup.py; all target volumes are exact stack-owned named volumes.
  docker run --rm --network none --user 0:0 --entrypoint /bin/sh \
    -v "$volume:/target" -v "$BACKUP:/backup:ro" "$ARCHIVE_IMAGE" \
    -c "find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar xzf /backup/$logical.tar.gz -C /target"
done

# Credentials in .env.private are NOT automatically imported. Only an operator
# can match them to a newly created isolated stack before invoking restore.
docker compose --env-file .env up -d
bash deploy/wait-stack.sh
bash deploy/migrate.sh
bash tests/qualification.sh
echo "RESTORE=PASS|stack_id=$STACK_ID"
echo 'NOTE: Database/volume restore completed. Compare service state and real adapter configuration before any LIVE use.'
