#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "AIOPS2_OFFLINE_MODE=PASS"
echo "GIT_REQUIRED=NO"
echo "INTERNET_REQUIRED=NO"
command -v docker >/dev/null || { echo "FAIL|DOCKER_MISSING"; exit 1; }
docker compose version >/dev/null || { echo "FAIL|DOCKER_COMPOSE_MISSING"; exit 1; }
test -f compose.yml || { echo "FAIL|COMPOSE_MISSING"; exit 1; }
test -f config/temporal/dynamicconfig/docker.yaml || { echo "FAIL|TEMPORAL_DYNAMICCONFIG_MISSING"; exit 1; }
for image in ${POSTGRES_IMAGE:-postgres:16-alpine} ${TEMPORAL_IMAGE:-temporalio/auto-setup:1.32.1} ${TEMPORAL_UI_IMAGE:-temporalio/ui:2.56.0} ${PROMETHEUS_IMAGE:-prom/prometheus:v3.14.0} ${GRAFANA_IMAGE:-grafana/grafana:13.2.2} ${GLPI_IMAGE:-glpi/glpi:11.0.9} ${N8N_IMAGE:-n8nio/n8n:2.40.6}; do
  docker image inspect "$image" >/dev/null 2>&1 || { echo "FAIL|IMAGE_MISSING|$image"; exit 1; }
done
docker compose --env-file .env config >/dev/null
echo "OFFLINE_PREFLIGHT=PASS"
