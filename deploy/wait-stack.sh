#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
TIMEOUT_SECONDS="${AIOPS_STACK_WAIT_TIMEOUT_SECONDS:-600}"
INTERVAL_SECONDS=2
HEALTHY_SERVICES=(aiops2-postgres aiops2-core aiops2-twin aiops2-evidence aiops2-policy aiops2-intelligence aiops2-copilot aiops2-worker aiops2-simulator aiops2-portal aiops2-temporal-postgres aiops2-temporal aiops2-glpi-db aiops2-prometheus aiops2-grafana)
elapsed=0
while (( elapsed < TIMEOUT_SECONDS )); do
  all_healthy=1
  for service in "${HEALTHY_SERVICES[@]}"; do
    if ! docker inspect "$service" >/dev/null 2>&1; then all_healthy=0; continue; fi
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$service")"
    [[ "$status" == healthy ]] || all_healthy=0
  done
  if (( all_healthy )); then
    break
  fi
  sleep "$INTERVAL_SECONDS"
  elapsed=$((elapsed + INTERVAL_SECONDS))
done
if (( elapsed >= TIMEOUT_SECONDS )); then
  echo "FAIL|stack_health_timeout|elapsed_seconds=$elapsed"
  for service in "${HEALTHY_SERVICES[@]}"; do
    docker inspect "$service" >/dev/null 2>&1 || continue
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$service")"
    [[ "$status" == healthy ]] || { echo "UNHEALTHY|$service|$status"; docker logs --tail 60 "$service" 2>&1 | tail -n 60; }
  done
  exit 1
fi
for service in aiops2-temporal-schema aiops2-temporal-namespace; do
  state="$(docker inspect --format '{{.State.Status}}' "$service")"
  code="$(docker inspect --format '{{.State.ExitCode}}' "$service")"
  [[ "$state" == exited && "$code" == 0 ]] || { echo "FAIL|bootstrap_job|$service|$state|$code"; docker logs --tail 100 "$service" 2>&1 || true; exit 1; }
done
echo "STACK_HEALTH=PASS|elapsed_seconds=$elapsed|temporal_schema=PASS|temporal_namespace=PASS"
