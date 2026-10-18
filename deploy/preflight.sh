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
chmod 600 .env
docker compose --env-file .env config >/dev/null
for p in 7777 8080 5678 9090 3000; do
  if ss -lnt 2>/dev/null | awk '{print $4}' | grep -Eq ":${p}$"; then echo "FAIL|PORT_IN_USE|$p"; exit 1; fi
done
echo 'PREFLIGHT=PASS'
