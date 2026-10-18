#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env config --quiet
for s in aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal aiops2-temporal-postgres aiops2-intelligence aiops2-rag aiops2-integration aiops2-glpi-db aiops2-glpi aiops2-n8n aiops2-prometheus aiops2-grafana aiops2-alertmanager; do
 STATUS=$(docker inspect -f '{{.State.Status}}' "$s") || { echo "FAIL|MISSING|$s";exit 1; }
 [ "$STATUS" = running ] || { echo "FAIL|NOT_RUNNING|$s|$STATUS";exit 1; }
done
[ "$(docker inspect -f '{{.State.ExitCode}}' aiops2-temporal-schema)" = 0 ] || { echo 'FAIL|TEMPORAL_SCHEMA';exit 1; }
curl -fsS http://127.0.0.1:7777/health >/dev/null
docker exec aiops2-temporal temporal operator cluster health --address 127.0.0.1:7233 >/dev/null
docker exec aiops2-temporal-ui wget -qO- http://127.0.0.1:8080 >/dev/null
curl -fsS http://127.0.0.1:19090/-/ready >/dev/null
curl -fsS http://127.0.0.1:13000/api/health >/dev/null
echo 'QUALIFICATION=PASS'
