#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
usage() {
  echo "Usage: bash deploy/upgrade.sh --plan | --apply --backup-dir /absolute/path --confirm-host HOSTNAME"
  echo "Default is read-only plan. Apply requires externally verified backups and explicit hostname confirmation."
}
MODE=plan
BACKUP_DIR=""
CONFIRM_HOST=""
while (($#)); do
  case "$1" in
    --plan) MODE=plan; shift ;;
    --apply) MODE=apply; shift ;;
    --backup-dir) [[ $# -ge 2 ]] || { usage; exit 2; }; BACKUP_DIR="$2"; shift 2 ;;
    --confirm-host) [[ $# -ge 2 ]] || { usage; exit 2; }; CONFIRM_HOST="$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done
bash deploy/debian-preflight.sh
[[ -f .env ]] || { echo "FAIL|existing_env_required_for_upgrade"; exit 1; }
echo "HOST=$(hostname)"
echo "SOURCE_SHA=$(git rev-parse HEAD 2>/dev/null || echo UNKNOWN)"
echo "COMPOSE_PROJECT=aiops2"
echo "MODE=$MODE"
echo "RUNNING_SERVICES_BEGIN"
docker compose --env-file .env ps --format json || true
echo "RUNNING_SERVICES_END"
echo "UPGRADE_DIFF_BEGIN"
docker compose --env-file .env config --services
echo "UPGRADE_DIFF_END"
if [[ "$MODE" == plan ]]; then
  echo "PLAN_ONLY=PASS|no_mutations"
  exit 0
fi
[[ "$BACKUP_DIR" == /* && -d "$BACKUP_DIR" ]] || { echo "FAIL|absolute_existing_backup_directory_required"; exit 1; }
[[ -f "$BACKUP_DIR/BACKUP-VERIFIED" ]] || { echo "FAIL|backup_verification_marker_missing"; exit 1; }
[[ "$CONFIRM_HOST" == "$(hostname)" ]] || { echo "FAIL|hostname_confirmation_mismatch"; exit 1; }
[[ "${AIOPS_UPGRADE_APPROVED:-0}" == 1 ]] || { echo "FAIL|set_AIOPS_UPGRADE_APPROVED_1_after_change_approval"; exit 1; }
echo "APPROVED_APPLY=1|backup_marker=$BACKUP_DIR/BACKUP-VERIFIED"
echo "NOTICE=No automatic database migrations or legacy retirement are performed by this script."
docker compose --env-file .env build
docker compose --env-file .env up -d --no-build
bash tests/qualification.sh
echo "UPGRADE=QUALIFICATION_PASSED|synthetic_e2e_not_run|rollback_manual"
