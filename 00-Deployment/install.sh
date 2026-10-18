#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
SRC="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${AIOPS2_ROOT:-/home/aiops/aiops2-v8}"
if [[ -e "$TARGET" ]]; then echo "FAIL|TARGET_EXISTS|$TARGET"; exit 2; fi
bash "$SRC/deploy/preflight.sh"
mkdir -p "$TARGET"
cp -a "$SRC/." "$TARGET/"
cd "$TARGET"
[[ -f .env ]] || cp config/.env.example .env
chmod 600 .env
if ! grep -q '^POSTGRES_PASSWORD=' .env; then cat >> .env <<'EOV'
POSTGRES_PASSWORD=Newaiops26$
GLPI_DB_PASSWORD=Newaiops26$
GLPI_DB_ROOT_PASSWORD=Newaiops26$
AIOPS_ADMIN_TOKEN=Newaiops26$
AIOPS_INTERNAL_TOKEN=Newaiops26$
GRAFANA_ADMIN_PASSWORD=Newaiops26$
N8N_ENCRYPTION_KEY=Newaiops26$-N8N
EOV
fi
chmod 600 .env
docker compose --env-file .env config >/dev/null
echo "PASS|INSTALL_TREE|$TARGET"
echo "NEXT|bash 00-Deployment/start.sh"
