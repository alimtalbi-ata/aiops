#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SRC="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="\${AIOPS2_ROOT:-/home/aiops/aiops2-v8}"
PASSWORD="\${AIOPS2_PASSWORD:-}"
if [[ -z "$PASSWORD" ]]; then
  echo "FAIL|PASSWORD_REQUIRED|Use AIOPS2_PASSWORD=..."
  exit 2
fi
if [[ -e "$TARGET" ]]; then echo "FAIL|TARGET_EXISTS|$TARGET"; exit 2; fi
bash "$SRC/deploy/preflight.sh"
mkdir -p "$TARGET"
cp -a "$SRC/." "$TARGET/"
cd "$TARGET"
cp config/.env.example .env
python3 - "$PASSWORD" <<'PY'
from pathlib import Path
import sys
p=Path(".env")
value=sys.argv[1]
lines=[]
for line in p.read_text().splitlines():
    if line.startswith(("POSTGRES_PASSWORD=","AIOPS_ADMIN_TOKEN=","AIOPS_INTERNAL_TOKEN=","GLPI_DB_PASSWORD=","GLPI_DB_ROOT_PASSWORD=","GRAFANA_ADMIN_PASSWORD=")):
        key=line.split("=",1)[0]
        lines.append(f"{key}={value}")
    elif line.startswith("N8N_ENCRYPTION_KEY="):
        lines.append(f"N8N_ENCRYPTION_KEY={value}-N8N")
    else:
        lines.append(line)
p.write_text("\n".join(lines)+"\n")
PY
chmod 600 .env
grep -Eq '^POSTGRES_PASSWORD=.+$' .env || { echo 'FAIL|EMPTY_POSTGRES_PASSWORD'; exit 2; }
grep -Eq '^GLPI_DB_PASSWORD=.+$' .env || { echo 'FAIL|EMPTY_GLPI_PASSWORD'; exit 2; }
grep -Eq '^AIOPS_ADMIN_TOKEN=.+$' .env || { echo 'FAIL|EMPTY_ADMIN_TOKEN'; exit 2; }
docker compose --env-file .env config >/dev/null
echo "PASS|ENV_CONFIG"
echo "PASS|INSTALL_TREE|$TARGET"
echo "NEXT|bash 00-Deployment/start.sh"
