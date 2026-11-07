#!/usr/bin/env bash
set -euo pipefail
echo "FS1125_MODE=READ_ONLY_PLATFORM_BASELINE_V2"
echo "FS1125_PRODUCTION_MUTATION=NONE"
echo "FS1125_TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo "=== GIT ==="
echo "FS1125_COMMIT=$(git -C "$(dirname "$0")/../.." rev-parse --short HEAD)"
echo "=== PORTAL HTTP ==="
for path in / /explorer/visual /explorer/prometheus /explorer/databases /explorer/cmdb; do
 code=$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "http://127.0.0.1:7777$path" 2>/dev/null || true)
 echo "ROUTE=$path HTTP=$code"
done
echo "=== SERVICE HEALTH ==="
for name in aiops2-rebuild-core aiops2-rebuild-worker aiops2-rebuild-twin aiops2-rebuild-intelligence aiops2-rebuild-policy aiops2-rebuild-evidence aiops2-rebuild-postgres aiops2-rebuild-temporal-postgres aiops2-rebuild-glpi-db aiops2-rebuild-prometheus aiops2-rebuild-temporal aiops2-rebuild-cloudbeaver; do
 docker inspect "$name" --format 'SERVICE={{.Name}} STATE={{.State.Status}} HEALTH={{if .State.Health}}{{.State.Health.Status}}{{else}}not-configured{{end}}' 2>/dev/null || echo "SERVICE=$name STATE=NOT_FOUND"
done
echo "=== DATABASE TCP VIA PYTHON SOCKET ==="
docker run --rm --network aiops2-rebuild-data python:3.12-alpine python -c 'import socket; h="aiops2-rebuild-postgres"; p=5432; s=socket.socket();s.settimeout(3);r=s.connect_ex((h,p));s.close();print("DB=core TCP="+("PASS" if r==0 else "FAIL"))'
docker run --rm --network aiops2-rebuild-temporal-data python:3.12-alpine python -c 'import socket; h="aiops2-rebuild-temporal-postgres"; p=5432; s=socket.socket();s.settimeout(3);r=s.connect_ex((h,p));s.close();print("DB=temporal TCP="+("PASS" if r==0 else "FAIL"))'
docker run --rm --network aiops2-rebuild-integration python:3.12-alpine python -c 'import socket; h="aiops2-rebuild-glpi-db"; p=3306; s=socket.socket();s.settimeout(3);r=s.connect_ex((h,p));s.close();print("DB=glpi TCP="+("PASS" if r==0 else "FAIL"))'
echo "=== CLOUDBEAVER ==="
echo "CLOUDBEAVER_HTTP=$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ 2>/dev/null || true)"
echo "FS1125_RESULT=BASELINE_V2_COMPLETE"
echo "FS1125_NOTE=HTTP_AND_TCP_DO_NOT_PROVE_BUSINESS_FUNCTIONALITY"
