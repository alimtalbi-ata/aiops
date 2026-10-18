#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
: "${CONFIRM_BIG_BANG:?Set CONFIRM_BIG_BANG=YES to authorize legacy retirement and deployment}"
[ "$CONFIRM_BIG_BANG" = YES ] || { echo 'FAIL|CONFIRM_BIG_BANG'; exit 2; }
bash deploy/preflight.sh
# Never retire the legacy stack before the new stack has passed qualification.
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull=false
docker compose --env-file .env up -d --remove-orphans
bash deploy/migrate.sh
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
if [ "${RETIRE_LEGACY:-0}" = 1 ]; then
  [ "${CONFIRM_RETIRE_AFTER_QUALIFICATION:-NO}" = YES ] || { echo 'RETIREMENT_GATE=BLOCKED|set CONFIRM_RETIRE_AFTER_QUALIFICATION=YES after qualification'; exit 3; }
  bash deploy/retire-legacy.sh
fi
echo 'BIG_BANG=QUALIFIED'
