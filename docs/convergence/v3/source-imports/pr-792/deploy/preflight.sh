#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
command -v docker >/dev/null || { echo 'FAIL|docker_missing'; exit 1; }
docker compose version >/dev/null || { echo 'FAIL|compose_missing'; exit 1; }
FREE_KB=$(df -Pk "$ROOT" | awk 'NR==2{print $4}')
(( FREE_KB > 8388608 )) || { echo "FAIL|disk_low|${FREE_KB}KB"; exit 1; }
[ -f compose.yml ] || { echo 'FAIL|compose_missing'; exit 1; }
[ -f config/.env.example ] || { echo 'FAIL|env_missing'; exit 1; }
bash deploy/init-env.sh
bash deploy/check-secrets.sh .env
docker compose --env-file .env config >/dev/null
echo 'PREFLIGHT=PASS'
for f in app/core/Dockerfile app/twin/Dockerfile app/evidence/Dockerfile app/policy/Dockerfile app/intelligence/Dockerfile app/copilot/Dockerfile app/worker/Dockerfile app/simulator/Dockerfile app/portal/Dockerfile deploy/Dockerfile.evaluator; do test -f "$f" || { echo "FAIL|MISSING_DOCKERFILE|$f"; exit 1; }; done
for key in AIOPS_PORTAL_HOST_PORT AIOPS_GLPI_HOST_PORT AIOPS_N8N_HOST_PORT AIOPS_PROMETHEUS_HOST_PORT AIOPS_GRAFANA_HOST_PORT; do grep -Fq "$key" compose.yml || { echo "FAIL|PORT_CONFIG|$key"; exit 1; }; done
for f in deploy/install-isolated.sh tests/isolated-deploy-contract.sh deploy/qualify-model.sh deploy/wait-stack.sh deploy/temporal/setup-postgres.sh deploy/temporal/create-namespace.sh tests/runtime-e2e.sh tests/temporal-contract.sh config/temporal/dynamicconfig/development-sql.yaml; do test -s "$f" || { echo "FAIL|MISSING_QUALIFICATION_SCRIPT|$f"; exit 1; }; done
echo DOCKERFILE_AND_PORT_CONTRACT=PASS
