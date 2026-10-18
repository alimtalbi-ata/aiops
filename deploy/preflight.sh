#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
command -v docker >/dev/null || { echo 'FAIL|docker_missing'; exit 1; }
docker compose version >/dev/null || { echo 'FAIL|compose_missing'; exit 1; }
FREE_KB=$(df -Pk "$ROOT" | awk 'NR==2{print $4}')
(( FREE_KB > 8388608 )) || { echo "FAIL|disk_low|${FREE_KB}KB"; exit 1; }
[ -f compose.yml ] || { echo 'FAIL|compose_missing'; exit 1; }
[ -f config/.env.example ] || { echo 'FAIL|env_missing'; exit 1; }
[ -f .env ] || cp config/.env.example .env
docker compose --env-file .env config >/dev/null
echo 'PREFLIGHT=PASS'
for f in app/core/Dockerfile app/twin/Dockerfile app/evidence/Dockerfile app/policy/Dockerfile app/copilot/Dockerfile app/worker/Dockerfile app/simulator/Dockerfile app/portal/Dockerfile; do test -f "$f" || { echo "FAIL|MISSING_DOCKERFILE|$f"; exit 1; }; done
for p in 7777:777 8080:80 5678:5678 9090:9090 3000:3000; do grep -q "$p" compose.yml || { echo "FAIL|PORT|$p"; exit 1; }; done
echo DOCKERFILE_AND_PORT_CONTRACT=PASS
