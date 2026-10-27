#!/usr/bin/env bash
# Read-only reconnaissance: no API tokens, no side effects, no external published ports.
set -u
echo "=== Containers (names, images, status only) ==="
docker ps --format '{{.Names}}|{{.Image}}|{{.Status}}' | grep -Ei 'glpi|grafana|n8n' || true
echo "=== Containers exact versions (no env dump) ==="
for name in $(docker ps --format '{{.Names}}' | grep -Ei 'glpi|grafana|n8n'); do
  echo "--- $name"
  docker inspect "$name" --format 'image={{.Config.Image}} state={{.State.Status}}' || true
done
echo "=== Local fixture validity ==="
python3 /home/aiops/aiops-demo-integrations-v21315/validate_fixture.py /home/aiops/aiops-demo-integrations-v21315/acme-fixtures.json
echo "=== Local files and sizes ==="
find /home/aiops/aiops-demo-integrations-v21315 -maxdepth 2 -type f -printf '%P %s bytes\n' | sort
echo "AIOPS_INTEGRATIONS_READ_ONLY_DISCOVERY=DONE"
