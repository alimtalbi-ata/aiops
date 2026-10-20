#!/usr/bin/env bash
# Read-only verification of the topology seed in the selected Compose project.
set -Eeuo pipefail
cd "$(dirname "$0")/.."
[[ -f .env ]] || { echo 'FAIL|missing_environment'; exit 2; }
DB_USER="$(sed -n 's/^POSTGRES_USER=//p' .env | head -1)"
DB_NAME="$(sed -n 's/^POSTGRES_DB=//p' .env | head -1)"
DB_USER="${DB_USER:-aiops}"
DB_NAME="${DB_NAME:-aiops}"
STACK_ID="$(sed -n 's/^AIOPS_STACK_ID=//p' .env | head -1)"
STACK_ID="${STACK_ID:-aiops2}"
CID="$(docker compose --env-file .env ps -q aiops2-postgres)"
[[ -n "$CID" ]] || { echo 'FAIL|selected_project_postgres_absent'; exit 3; }
OWNER="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$CID")"
[[ "$OWNER" == "$STACK_ID" ]] || { echo 'FAIL|postgres_project_identity_mismatch'; exit 3; }
COUNT="$(docker compose --env-file .env exec -T aiops2-postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atqc 'select count(*) from aiops.twin_nodes')"
[[ "$COUNT" =~ ^[0-9]+$ && "$COUNT" -gt 0 ]] || { echo "FAIL|acme_topology_seed_empty|$COUNT"; exit 4; }
echo "TWIN_SEED=PASS|stack_id=$STACK_ID|nodes=$COUNT"
