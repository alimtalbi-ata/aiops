#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
: "${CONFIRM_BIG_BANG:?Set CONFIRM_BIG_BANG=YES to authorize legacy retirement and deployment}"
[ "$CONFIRM_BIG_BANG" = YES ] || { echo 'FAIL|CONFIRM_BIG_BANG'; exit 2; }
bash deploy/preflight.sh
if [ "${RETIRE_LEGACY:-1}" = 1 ]; then bash deploy/retire-legacy.sh; fi
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull
docker compose --env-file .env up -d --remove-orphans
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
echo 'BIG_BANG=QUALIFIED'
