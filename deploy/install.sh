#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
if [[ "${RETIRE_LEGACY:-0}" == 1 ]]; then
  echo "FAIL|legacy_retirement_requires_separate_postqualification_operation"
  exit 6
fi
bash deploy/init-env.sh
bash deploy/preflight.sh
# Legacy retirement is deliberately separate and explicit.
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull
docker compose --env-file .env up -d
bash deploy/wait-stack.sh
bash deploy/migrate.sh
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
