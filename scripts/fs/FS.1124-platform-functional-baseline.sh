#!/usr/bin/env bash
set -euo pipefail
echo "FS1124_MODE=READ_ONLY_PLATFORM_FUNCTIONAL_BASELINE"
echo "FS1124_PRODUCTION_MUTATION=NONE"
echo "FS1124_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=== CONTAINERS ==="
docker ps --format '{{.Names}}|{{.Status}}|{{.Image}}' | grep -Ei 'aiops2|prometheus|temporal|glpi' | sort || true
echo "=== PORTAL ROUTES ==="
for path in / /explorer/visual /explorer/prometheus /explorer/databases /explorer/cmdb; do
 code=$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:7777$path" 2>/dev/null || true)
 echo "ROUTE=$path HTTP=$code"
done
echo "=== CLOUDBEAVER ==="
echo "HTTP=$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ 2>/dev/null || true)"
echo "=== DATABASE CONNECTIVITY ==="
for pair in 'aiops2-rebuild-postgres:5432' 'aiops2-rebuild-temporal-postgres:5432' 'aiops2-rebuild-glpi-db:3306'; do
 host=${pair%:*};port=${pair#*:}
 if docker exec aiops2-rebuild-cloudbeaver sh -c "timeout 3 sh -c 'echo > /dev/tcp/$host/$port'" >/dev/null 2>&1; then
  echo "DB=$host TCP=PASS"
 else
  echo "DB=$host TCP=UNVERIFIED"
 fi
done
echo "=== GIT WORKTREE ==="
git rev-parse --short HEAD
echo "=== FS1124_RESULT=BASELINE_COLLECTED_NO_CHANGES ==="
