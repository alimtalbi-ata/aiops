#!/usr/bin/env bash
# FS621 single controlled cutover. Requires explicit operator confirmation.
set -Eeuo pipefail
[[ "${DEPLOY_FS621:-}" == "YES" ]] || { echo "Set DEPLOY_FS621=YES only after acceptance checks"; exit 2; }
: "${COMPOSE_FILE:?Set absolute path to the running stack compose file}"
: "${EXPLORER_ALLOWED_CIDRS:?Set trusted administration CIDRs; no user login required}"
[[ -f "$COMPOSE_FILE" ]] || { echo "Compose file missing"; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${CANDIDATE_IMAGE:-aiops2-portal:fs621-explorers-candidate}"
docker image inspect "$IMAGE" >/dev/null
PROJECT="${COMPOSE_PROJECT_NAME:-aiops2-rebuild}"
SERVICE="${PORTAL_SERVICE:-aiops2-portal}"
CURRENT="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')"
[[ -n "$CURRENT" ]] || exit 2
BACKUP="${HOME}/aiops2-backups/FS621-$(date -u +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
chmod 700 "$BACKUP"
printf '%s\n' "$CURRENT" > "$BACKUP/previous-image.txt"
# Compose overlay contains no DB secrets; existing service environment is retained.
python3 - "$BACKUP/overlay.json" <<'PY'
import json,os,sys
env={"EXPLORER_ENABLED":"1","EXPLORER_ALLOWED_CIDRS":os.environ["EXPLORER_ALLOWED_CIDRS"]}
for key in ("EXPLORER_PROMETHEUS_URL","EXPLORER_LOKI_URL","EXPLORER_TEMPO_URL",
            "EXPLORER_CMDB_URL","EXPLORER_TEMPORAL_UI_URL","EXPLORER_N8N_URL",
            "EXPLORER_CORE_PG_DSN","EXPLORER_TEMPORAL_PG_DSN","EXPLORER_GLPI_MYSQL_DSN"):
    if os.environ.get(key):
        env[key]=os.environ[key]
with open(sys.argv[1],"w") as f:
    json.dump({"services":{os.environ.get("PORTAL_SERVICE","aiops2-portal"):
          {"image":os.environ.get("CANDIDATE_IMAGE","aiops2-portal:fs621-explorers-candidate"),
           "environment":env}}},f)
PY
chmod 600 "$BACKUP/overlay.json"
docker compose -p "$PROJECT" -f "$COMPOSE_FILE" -f "$BACKUP/overlay.json" config -q
echo "ROLLBACK_IMAGE=$CURRENT"
echo "BACKUP_DIR=$BACKUP"
docker compose -p "$PROJECT" -f "$COMPOSE_FILE" -f "$BACKUP/overlay.json" up -d --no-deps --no-build "$SERVICE"
# Public health and anonymous page smoke checks; SQL data is never fetched here.
python3 - <<'PY'
import urllib.request
for path in ("/health", "/openapi.json"):
    with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=12) as r:
        assert r.status==200,(path,r.status)
print("PORTAL_HEALTH_OK")
PY
echo "DEPLOYED_IMAGE=$IMAGE"
echo "Rollback: use the same compose file with an overlay image=$CURRENT and the original environment."
echo "No GLPI, HITL, remediation, or run execution endpoints invoked."
