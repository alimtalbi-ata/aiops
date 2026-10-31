#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
bash deploy/init-env.sh
bash deploy/preflight.sh
# Legacy retirement is deliberately separate and explicit.
if [ "${RETIRE_LEGACY:-0}" = 1 ]; then bash deploy/retire-legacy.sh; fi
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull
# Start PostgreSQL first. The entrypoint applies only baseline migrations 000-008.
docker compose --env-file .env up -d --wait aiops2-postgres
# Apply 009+ through the checksum-journaled transactional migration runner.
bash deploy/migrate.sh
# Start the full stack only after the schema upgrade is recorded.
docker compose --env-file .env up -d --wait
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
