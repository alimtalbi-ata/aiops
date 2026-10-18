#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash deploy/preflight.sh

docker compose --env-file .env build --pull
docker compose --env-file .env up -d --remove-orphans

# Never report a successful start before the runtime qualification and E2E smoke test.
bash tests/qualification.sh
bash tests/synthetic-e2e.sh

docker compose --env-file .env ps
echo "AIOPS2_START=QUALIFIED"
