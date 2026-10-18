#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
bash deploy/preflight.sh
bash 00-Deployment/offline-preflight.sh
docker compose --env-file .env up -d --no-build --pull never --remove-orphans
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
docker compose --env-file .env ps
echo 'AIOPS2_START=QUALIFIED'
