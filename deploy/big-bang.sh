#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
: "${CONFIRM_BIG_BANG:?Set CONFIRM_BIG_BANG=YES to authorize legacy retirement and deployment}"
[ "$CONFIRM_BIG_BANG" = YES ] || { echo 'FAIL|CONFIRM_BIG_BANG'; exit 2; }
bash deploy/preflight.sh
if [ "${RETIRE_LEGACY:-0}" = 1 ]; then
  [[ "${CONFIRM_LEGACY_RETIRE:-0}" == YES ]] || { echo "FAIL|legacy_retirement_requires_separate_confirmation"; exit 2; }
  bash deploy/retire-legacy.sh
fi
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull
docker compose --env-file .env up -d --remove-orphans
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
echo 'BIG_BANG=QUALIFIED'
