#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
CID=$(docker ps --filter name=^/aiops-postgres$ --format '{{.ID}}'); test -n "$CID"
docker exec "$CID" psql -U "${POSTGRES_USER:-aiops}" -d "${POSTGRES_DB:-aiops}" -c 'select count(*) from aiops.twin_nodes' >/dev/null
echo TWIN_SEED=PASS
