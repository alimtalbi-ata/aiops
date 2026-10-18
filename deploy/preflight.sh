#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
command -v docker >/dev/null || { echo 'FAIL|DOCKER_MISSING'; exit 1; }
docker compose version >/dev/null || { echo 'FAIL|COMPOSE_MISSING'; exit 1; }
command -v python3 >/dev/null || { echo 'FAIL|PYTHON_MISSING'; exit 1; }
[ -s .env ] || { echo 'FAIL|ENV_MISSING'; exit 1; }
[ -s config/temporal/dynamicconfig/docker.yaml ] || { echo 'FAIL|DYNAMICCONFIG_MISSING'; exit 1; }
python3 - <<'PY'
from pathlib import Path
import sys
values={}
for line in Path('.env').read_text().splitlines():
 if '=' in line and not line.startswith('#'):
  k,v=line.split('=',1);values[k]=v
for key in ('POSTGRES_PASSWORD','AIOPS_ADMIN_TOKEN','AIOPS_INTERNAL_TOKEN','GLPI_DB_PASSWORD','GLPI_DB_ROOT_PASSWORD','GRAFANA_ADMIN_PASSWORD','N8N_ENCRYPTION_KEY'):
 if not values.get(key):sys.exit('FAIL|EMPTY_SECRET|'+key)
PY
docker compose --env-file .env config --quiet
bash tests/static-audit.sh
bash tests/sql-audit.sh
bash tests/runtime-contract.sh
echo 'PREFLIGHT=PASS'
