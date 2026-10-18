#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env config >/dev/null
SERVICES='aiops-postgres aiops-core aiops-twin aiops-evidence aiops-policy aiops-copilot aiops-worker aiops-integration aiops-simulator aiops-portal aiops-temporal aiops-temporal-postgres aiops-temporal-ui aiops-glpi-db aiops-glpi aiops-n8n aiops-prometheus aiops-grafana aiops-alertmanager aiops-rag aiops-intelligence'
for s in $SERVICES; do docker inspect "$s" >/dev/null 2>&1 || { echo "FAIL|MISSING|$s"; exit 1; }; done
for pair in aiops-core:810 aiops-twin:811 aiops-evidence:812 aiops-policy:813 aiops-copilot:814 aiops-worker:815 aiops-simulator:816 aiops-integration:817 aiops-rag:819 aiops-intelligence:818; do
 svc=${pair%%:*}; port=${pair##*:}; docker exec "$svc" python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${port}/health',timeout=3).read()" >/dev/null || { echo "FAIL|INTERNAL_HEALTH|$svc:$port"; exit 1; }
done
curl -fsS http://127.0.0.1:7777/health >/dev/null
curl -fsS http://127.0.0.1:8080 >/dev/null
curl -fsS http://127.0.0.1:9090/-/ready >/dev/null
curl -fsS http://127.0.0.1:3000/api/health >/dev/null
# Only external interfaces may be published on the host.
if docker compose ps --format json | grep -Eq 'PublishedPort.{0,20}(777|810|811|812|813|814|815|816|817|7233)'; then echo 'FAIL|FORBIDDEN_INTERNAL_PORT_PUBLISHED'; exit 1; fi
echo QUALIFICATION=PASS
