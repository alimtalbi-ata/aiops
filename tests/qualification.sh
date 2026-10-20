#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
STACK_ID="$(sed -n 's/^AIOPS_STACK_ID=//p' .env | head -1)"
STACK_ID="${STACK_ID:-aiops2}"
docker compose --env-file .env config >/dev/null
bash deploy/migrate.sh
# Container existence and process health are separate assertions.
for s in aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-intelligence aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal aiops2-temporal-ui aiops2-temporal-postgres aiops2-glpi-db aiops2-glpi aiops2-n8n aiops2-prometheus aiops2-grafana aiops2-alertmanager; do
  container="${STACK_ID}-${s#aiops2-}"
  docker inspect "$container" >/dev/null 2>&1 || { echo "FAIL|MISSING|$s"; exit 1; }
  state="$(docker inspect --format '{{.State.Status}}' "$container")"
  [[ "$state" == running ]] || { echo "FAIL|NOT_RUNNING|$s|$state"; exit 1; }
done
for s in aiops2-temporal-schema aiops2-temporal-namespace; do
  container="${STACK_ID}-${s#aiops2-}"
  state="$(docker inspect --format '{{.State.Status}}' "$container")"
  code="$(docker inspect --format '{{.State.ExitCode}}' "$container")"
  [[ "$state" == exited && "$code" == 0 ]] || { echo "FAIL|TEMPORAL_BOOTSTRAP|$s|$state|$code"; exit 1; }
done
for s in aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-intelligence aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal aiops2-temporal-postgres aiops2-glpi-db aiops2-prometheus aiops2-grafana; do
  container="${STACK_ID}-${s#aiops2-}"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}not-configured{{end}}' "$container")"
  [[ "$health" == healthy ]] || { echo "FAIL|UNHEALTHY|$s|$health"; exit 1; }
done
curl -fsS "http://127.0.0.1:$(sed -n 's/^AIOPS_PORTAL_HOST_PORT=//p' .env | head -1)/health" >/dev/null
curl -fsS "http://127.0.0.1:$(sed -n 's/^AIOPS_GLPI_HOST_PORT=//p' .env | head -1)" >/dev/null
curl -fsS "http://127.0.0.1:$(sed -n 's/^AIOPS_PROMETHEUS_HOST_PORT=//p' .env | head -1)/-/ready" >/dev/null
curl -fsS "http://127.0.0.1:$(sed -n 's/^AIOPS_GRAFANA_HOST_PORT=//p' .env | head -1)/api/health" >/dev/null
echo QUALIFICATION=PASS
