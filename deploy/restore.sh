#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
BACKUP="${1:?Usage: CONFIRM_RESTORE=YES CONFIRM_TARGET_DATABASES=YES deploy/restore.sh <backup-directory>}"
[[ "${CONFIRM_RESTORE:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_RESTORE=YES'; exit 2; }
[[ "${CONFIRM_TARGET_DATABASES:-}" == YES ]] || { echo 'FAIL|set_CONFIRM_TARGET_DATABASES=YES'; exit 3; }
[[ -f "$BACKUP/aiops.dump" && -f "$BACKUP/temporal.dump" ]] || { echo 'FAIL|backup_files_missing'; exit 4; }
[[ -f .env ]] || { echo 'FAIL|missing_env'; exit 5; }
# This operation overwrites objects in the configured target databases.
docker compose --env-file .env exec -T aiops2-postgres pg_restore --clean --if-exists --no-owner -U aiops -d aiops < "$BACKUP/aiops.dump"
docker compose --env-file .env exec -T aiops2-temporal-postgres pg_restore --clean --if-exists --no-owner -U temporal -d temporal < "$BACKUP/temporal.dump"
echo 'RESTORE=COMMANDS_COMPLETED'
echo 'Run deploy/migrate.sh and tests/qualification.sh, then inspect application and restore logs before declaring recovery complete.'
