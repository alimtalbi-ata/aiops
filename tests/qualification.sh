#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
docker compose --env-file .env config >/dev/null
ALL_SERVICES=(aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal aiops2-temporal-admin-tools aiops2-temporal-postgres aiops2-glpi-db aiops2-glpi aiops2-n8n aiops2-prometheus aiops2-grafana aiops2-alertmanager)
for s in "${ALL_SERVICES[@]}"; do
  docker inspect "$s" >/dev/null 2>&1 || { echo "FAIL|MISSING|$s"; exit 1; }
done
APP_SERVICES=(aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal)
READY=0
for attempt in $(seq 1 90); do
  READY=1
  for s in "${APP_SERVICES[@]}"; do
    HEALTH="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$s")"
    if [[ "$HEALTH" != "healthy" ]]; then READY=0; break; fi
  done
  [[ "$READY" == "1" ]] && break
  sleep 2
done
if [[ "$READY" != "1" ]]; then
  for s in "${APP_SERVICES[@]}"; do
    docker inspect -f '{{.Name}}={{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$s" || true
  done
  echo 'FAIL|APP_HEALTH_TIMEOUT'
  exit 1
fi
wait_http() {
  local url="$1" label="$2"
  for attempt in $(seq 1 60); do
    if curl -fsS "$url" >/dev/null; then
      echo "HEALTHY|$label"
      return 0
    fi
    sleep 2
  done
  echo "FAIL|HTTP_READINESS_TIMEOUT|$label"
  return 1
}
wait_http http://127.0.0.1:7777/health portal
wait_http http://127.0.0.1:8080/ glpi
wait_http http://127.0.0.1:5678/healthz n8n
wait_http http://127.0.0.1:9090/-/ready prometheus
wait_http http://127.0.0.1:3000/api/health grafana
wait_http http://127.0.0.1:9093/-/ready alertmanager
echo QUALIFICATION=PASS
