#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
bash deploy/init-env.sh
bash deploy/preflight.sh
# Legacy retirement is deliberately separate and explicit.
if [ "${RETIRE_LEGACY:-0}" = 1 ]; then bash deploy/retire-legacy.sh; fi
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull
docker compose --env-file .env up -d
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
