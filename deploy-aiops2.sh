#!/usr/bin/env bash
set -Eeuo pipefail

cd /home/aiops/aiops-v28-demo

FILES=(
  -f compose.yml
  -f compose.demo-local.yml
  -f compose.llm-test.yml
  -f compose.dgx-network.yml
  -f compose.portal-restored.yml
  -f compose.n8n-restored.yml
  -f compose.alertmanager-restored.yml
)

echo "=== VALIDATION ==="
docker compose --profile test "${FILES[@]}" config --quiet

echo "=== SIMULATION ==="
docker compose --profile test "${FILES[@]}" \
  --dry-run up -d --no-recreate --no-build --pull never

echo
echo "Simulation terminée. Aucun conteneur modifié."
