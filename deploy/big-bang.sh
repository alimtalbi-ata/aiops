#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
: "${CONFIRM_BIG_BANG:?Set CONFIRM_BIG_BANG=YES to authorize legacy retirement and deployment}"
[ "$CONFIRM_BIG_BANG" = YES ] || { echo 'FAIL|CONFIRM_BIG_BANG'; exit 2; }
bash deploy/preflight.sh
if [[ "${RETIRE_LEGACY:-0}" == 1 ]]; then
  echo "FAIL|retire_legacy_only_as_independent_verified_postdeployment_action"
  exit 6
fi
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull
docker compose --env-file .env up -d --remove-orphans
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
echo 'BIG_BANG=QUALIFIED'
