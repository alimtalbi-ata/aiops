#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
BACKUP="${1:?Usage: CONFIRM_RESTORE=YES CONFIRM_TARGET_DATABASES=YES deploy/restore.sh <backup-directory>}"
[[ "${CONFIRM_RESTORE:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_RESTORE=YES'; exit 2; }
[[ "${CONFIRM_TARGET_DATABASES:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_TARGET_DATABASES=YES'; exit 3; }
[[ -d "$BACKUP" ]] || { echo "FAIL|backup_directory_missing"; exit 3; }
BACKUP="$(cd "$BACKUP" && pwd)"
[[ -f "$BACKUP/aiops.dump" && -f "$BACKUP/n8n.dump" && -f "$BACKUP/temporal.dump" && -f "$BACKUP/glpi-mariadb.sql" ]] || { echo 'FAIL|backup_files_missing'; exit 4; }
[[ -f .env ]] || { echo 'FAIL|missing_env'; exit 5; }
(
 cd "$BACKUP"
 sha256sum -c SHA256SUMS
)
# This operation overwrites the configured databases and service volumes.
VOLUME_IMAGE="$(docker inspect --format '{{.Config.Image}}' aiops2-postgres)"
docker compose --env-file .env exec -T aiops2-postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$BACKUP/aiops.dump"
docker compose --env-file .env exec -T aiops2-postgres sh -c 'pg_restore --clean --if-exists --no-owner -U "$POSTGRES_USER" -d n8n' < "$BACKUP/n8n.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres pg_restore --clean --if-exists --no-owner -U temporal -d temporal < "$BACKUP/temporal.dump"
docker compose --env-file .env exec -T aiops2-glpi-db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"' < "$BACKUP/glpi-mariadb.sql"
for volume in aiops2-n8n-data aiops2-glpi-data aiops2-grafana-data aiops2-prometheus-data; do
  [[ -f "$BACKUP/$volume.tar.gz" ]] || { echo "FAIL|missing_volume_archive|$volume"; exit 6; }
  docker run --rm --network none -v "$volume:/target" -v "$BACKUP:/backup:ro" "$VOLUME_IMAGE" sh -c "find /target -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar xzf /backup/$volume.tar.gz -C /target"
done
echo 'RESTORE=COMMANDS_COMPLETED'
echo 'Run deploy/migrate.sh, tests/qualification.sh and tests/synthetic-e2e.sh; inspect service logs and compare application counts before declaring recovery complete.'
