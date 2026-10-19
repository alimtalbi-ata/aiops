#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env config >/dev/null
bash deploy/migrate.sh
# Container existence and process health are separate assertions.
for s in aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-intelligence aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal aiops2-temporal-postgres aiops2-glpi-db aiops2-glpi aiops2-n8n aiops2-prometheus aiops2-grafana aiops2-alertmanager; do
  docker inspect "$s" >/dev/null 2>&1 || { echo "FAIL|MISSING|$s"; exit 1; }
  state="$(docker inspect --format '{{.State.Status}}' "$s")"
  [[ "$state" == running ]] || { echo "FAIL|NOT_RUNNING|$s|$state"; exit 1; }
done
for s in aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-intelligence aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal-postgres aiops2-glpi-db aiops2-prometheus aiops2-grafana; do
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}not-configured{{end}}' "$s")"
  [[ "$health" == healthy ]] || { echo "FAIL|UNHEALTHY|$s|$health"; exit 1; }
done
curl -fsS http://127.0.0.1:7777/health >/dev/null
curl -fsS http://127.0.0.1:8080 >/dev/null
curl -fsS http://127.0.0.1:9090/-/ready >/dev/null
curl -fsS http://127.0.0.1:3000/api/health >/dev/null
echo QUALIFICATION=PASS
