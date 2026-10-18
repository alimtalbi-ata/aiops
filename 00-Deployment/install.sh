#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=${AIOPS2_ROOT:-/home/aiops/aiops2-v8}
[[ ! -e "$ROOT" ]] || { echo "BLOCKED|TARGET_EXISTS|$ROOT"; exit 2; }
command -v docker >/dev/null || { echo 'FAIL|DOCKER'; exit 1; }
docker compose version >/dev/null || { echo 'FAIL|COMPOSE'; exit 1; }
free=$(df -Pm /home|awk 'NR==2{print $4}'); ((free>=4096)) || { echo "FAIL|DISK|${free}MB"; exit 1; }
mkdir -p "$ROOT"; cp -a "$(cd "$(dirname "$0")/..";pwd)/." "$ROOT/"
cd "$ROOT/00-Deployment"
docker compose config >/dev/null
echo "PASS|INSTALL_TREE|$ROOT"
echo "NEXT|docker compose up -d --build"
