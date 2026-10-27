#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo "PREFLIGHT_MODE=READ_ONLY"
if [[ ! -r /etc/os-release ]]; then echo "FAIL|os_release_missing"; exit 1; fi
. /etc/os-release
echo "OS_ID=${ID:-unknown}"
echo "OS_VERSION=${VERSION_ID:-unknown}"
[[ "${ID:-}" == "debian" ]] || { echo "FAIL|debian_required"; exit 1; }
for tool in docker openssl python3 curl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "FAIL|missing_tool|$tool"; exit 1; }
done
docker compose version >/dev/null || { echo "FAIL|docker_compose_unavailable"; exit 1; }
docker info >/dev/null 2>&1 || { echo "FAIL|docker_daemon_unavailable_or_denied"; exit 1; }
[[ -f compose.yml ]] || { echo "FAIL|compose_missing"; exit 1; }
if [[ -f .env ]]; then
  echo "ENV=EXISTING_PRESERVED"
  bash deploy/preflight.sh
  docker compose --env-file .env config --quiet
else
  echo "ENV=ABSENT_NEW_INSTALL_ONLY"
  echo "NOTE=upgrade_requires_existing_env"
fi
echo "DISK_AVAILABLE_KB=$(df -Pk "$ROOT" | awk 'END {print $4}')"
echo "PREFLIGHT=PASS"
