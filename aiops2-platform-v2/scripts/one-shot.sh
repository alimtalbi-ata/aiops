#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
MODE="${1:-}"
[[ "$MODE" == "--install" || "$MODE" == "--check" ]] || { echo "Usage: $0 --check | --install"; exit 2; }
SRC="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
DEST=/home/aiops/aiops2
command -v docker >/dev/null || { echo "DOCKER_MISSING"; exit 10; }
docker compose version >/dev/null
if [[ "$MODE" == "--check" ]]; then echo "SOURCE=$SRC"; echo "DESTINATION=$DEST"; echo "CHECK_ONLY=PASS"; exit 0; fi
if [[ -e "$DEST/00-Deployment" ]]; then echo "REFUSING_TO_OVERWRITE=$DEST"; exit 12; fi
mkdir -p "$DEST"
[[ -z "$(find "$DEST" -mindepth 1 -maxdepth 1 -print -quit)" ]] || { echo "DESTINATION_NOT_EMPTY=$DEST"; exit 13; }
cp -a "$SRC/." "$DEST/"
mkdir -p "$DEST/reports" "$DEST/data" "$DEST/backups"
chmod 700 "$DEST" "$DEST/reports" "$DEST/data" "$DEST/backups"
if [[ ! -f "$DEST/.env" ]]; then
 API_KEY="$(python3 -c 'import secrets;print(secrets.token_urlsafe(36))')"
 DB_PASSWORD="$(python3 -c 'import secrets;print(secrets.token_urlsafe(36))')"
 printf 'AIOPS2_API_PORT=18080\nAIOPS2_API_KEY=%s\nPOSTGRES_DB=aiops2\nPOSTGRES_USER=aiops2\nPOSTGRES_PASSWORD=%s\nLOG_LEVEL=INFO\n' "$API_KEY" "$DB_PASSWORD" > "$DEST/.env"
 chmod 600 "$DEST/.env"
fi
cd "$DEST"
docker compose --env-file .env -f 00-Deployment/compose.yml config --quiet
docker compose --env-file .env -f 00-Deployment/compose.yml build api
docker compose --env-file .env -f 00-Deployment/compose.yml up -d
ok=0
for i in $(seq 1 60); do if curl --fail --silent http://127.0.0.1:18080/ready >/dev/null; then ok=1;break;fi;sleep 2;done
if [[ "$ok" != 1 ]]; then docker compose --env-file .env -f 00-Deployment/compose.yml ps > "$DEST/reports/compose-ps.txt" 2>&1 || true;docker compose --env-file .env -f 00-Deployment/compose.yml logs --no-color --tail=250 > "$DEST/reports/compose-logs.txt" 2>&1 || true;echo "DEPLOYMENT_HEALTH=FAIL";exit 20;fi
AIOPS2_ENV_FILE="$DEST/.env" "$DEST/03-Tests/smoke-test.sh" | tee "$DEST/reports/smoke-test.txt"
docker compose --env-file .env -f 00-Deployment/compose.yml ps > "$DEST/reports/compose-ps.txt"
echo "DEPLOYMENT=PASS";echo "API=http://127.0.0.1:18080";echo "REPORTS=$DEST/reports";echo "API_KEY_PATH=$DEST/.env (keep private)"