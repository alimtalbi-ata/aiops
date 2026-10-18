#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
[ -f .env ] || { cp config/.env.example .env; chmod 600 .env; }
bash tests/static-audit.sh
bash deploy/preflight.sh
docker compose --env-file .env config >/dev/null
docker compose --env-file .env build --pull=false
docker compose --env-file .env up -d
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
