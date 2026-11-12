#!/usr/bin/env bash
# FS624 — controlled one-time cutover; never replaces the existing compose stack.
set -Eeuo pipefail
[[ "${DEPLOY_FS621:-}" == "YES" ]] || { echo "Refusing: explicit DEPLOY_FS621=YES required"; exit 2; }
[[ "${FS621_ACCEPTANCE_COMPLETE:-}" == "YES" ]] || { echo "Refusing: FS621 acceptance not complete"; exit 2; }
[[ "${FS621_NETWORK_PERIMETER_VERIFIED:-}" == "YES" ]] || { echo "Refusing: network perimeter unverified"; exit 2; }
[[ "${FS621_SQL_ROLES_VERIFIED:-}" == "YES" ]] || { echo "Refusing: SQL roles unverified"; exit 2; }
[[ "${FS621_SECRETS_READY:-}" == "YES" ]] || { echo "Refusing: operational Compose secrets have not been verified"; exit 2; }
for key in AIOPS_ADMIN_TOKEN AIOPS_INTERNAL_TOKEN CORE_URL GLPI_API_URL GLPI_APP_TOKEN GLPI_USER_TOKEN; do
  [[ -n "${!key:-}" ]] || { echo "Refusing: required Compose variable $key not set"; exit 2; }
done
: "${EXPLORER_ALLOWED_CIDRS:?Trusted network CIDRs required}"
[[ "$EXPLORER_ALLOWED_CIDRS" == "10.79.94.0/24" ]] || { echo "Refusing: unexpected CIDR"; exit 2; }
: "${COMPOSE_FILES:?Three original compose files required, colon separated, in original order}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${CANDIDATE_IMAGE:-aiops2-portal:fs621-explorers-candidate}"
PROJECT="aiops2-rebuild"
SERVICE="aiops2-portal"
CONTAINER="aiops2-rebuild-portal"
docker image inspect "$IMAGE" >/dev/null
IFS=: read -r -a INPUT_FILES <<< "$COMPOSE_FILES"
[[ "${#INPUT_FILES[@]}" -eq 3 ]] || { echo "Refusing: expected exactly 3 compose files"; exit 2; }
EXPECTED="/home/aiops/aiops2-patches/fs-portal-real-fs225/compose.fs274.yml:/home/aiops/aiops2-patches/fs-glpi-technician-fs286/compose.fs292.yml:/home/aiops/aiops2-backups/FS569-portal-deployment/compose.fs569.yml"
[[ "$COMPOSE_FILES" == "$EXPECTED" ]] || { echo "Refusing: compose file order differs from running container"; exit 2; }
ARGS=()
for f in "${INPUT_FILES[@]}"; do [[ -r "$f" ]] || { echo "Missing compose file: $f"; exit 2; }; ARGS+=(-f "$f"); done
[[ "$(docker inspect "$CONTAINER" --format '{{index .Config.Labels "com.docker.compose.project"}}')" == "$PROJECT" ]] || exit 2
[[ "$(docker inspect "$CONTAINER" --format '{{index .Config.Labels "com.docker.compose.service"}}')" == "$SERVICE" ]] || exit 2
CURRENT="$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')"
[[ "$CURRENT" == "aiops2-portal:fs563-glpi-ownership-candidate-20261106" ]] || { echo "Refusing: unexpected current image"; exit 2; }
BACKUP="$HOME/aiops2-backups/FS624-$(date -u +%Y%m%d-%H%M%S)"
umask 077
mkdir -p "$BACKUP"
trap 'rm -f "$BACKUP/overlay.json" "$BACKUP/merged.json"' EXIT
printf '%s\n' "$CURRENT" > "$BACKUP/previous-image.txt"
# No environment or secrets are dumped. The original compose stack is retained.
python3 - "$BACKUP/overlay.json" <<'PY'
import json,os,sys
env={"EXPLORER_ENABLED":"1","EXPLORER_ALLOWED_CIDRS":os.environ["EXPLORER_ALLOWED_CIDRS"],"EXPLORER_PROMETHEUS_URL":"http://aiops2-prometheus:9090","EXPLORER_LOKI_URL":"http://aiops2-demo-observability-demo-loki-1:3100","EXPLORER_TEMPO_URL":"http://aiops2-demo-observability-demo-tempo-1:3200"}
for key in ("EXPLORER_PROMETHEUS_URL","EXPLORER_LOKI_URL","EXPLORER_TEMPO_URL",
            "EXPLORER_CMDB_URL","EXPLORER_TEMPORAL_UI_URL","EXPLORER_N8N_URL",
            "EXPLORER_CORE_PG_DSN","EXPLORER_TEMPORAL_PG_DSN","EXPLORER_GLPI_MYSQL_DSN"):
    if os.environ.get(key):
        env[key]=os.environ[key]
with open(sys.argv[1],"w") as f:
    json.dump({"services":{"aiops2-portal":{"image":os.environ.get("CANDIDATE_IMAGE","aiops2-portal:fs621-explorers-candidate"),"environment":env,"networks":{n:{} for n in ("aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public","aiops2-rebuild-observability")}}},"networks":{n:{"external":True,"name":n} for n in ("aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public","aiops2-rebuild-observability")}},f)
PY
docker network inspect aiops2-rebuild-observability --format '{{.Internal}}' | grep -qx true || { echo "Observability network is not internal"; exit 2; }
docker compose -p "$PROJECT" "${ARGS[@]}" -f "$BACKUP/overlay.json" config --format json > "$BACKUP/merged.json"
python3 - "$BACKUP/merged.json" <<'PY_NETWORKS'
import json,sys
with open(sys.argv[1]) as f: c=json.load(f)
actual=set(c["services"]["aiops2-portal"].get("networks",{}))
required={"aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public","aiops2-rebuild-observability"}
if not required.issubset(actual):
    raise SystemExit("Refusing: portal network preservation check failed")
print("PORTAL_NETWORKS_PRESERVED=YES")
PY_NETWORKS
python3 - "$BACKUP/merged.json" <<'PY_ENV'
import json,os,sys
with open(sys.argv[1]) as f: c=json.load(f)
actual=c["services"]["aiops2-portal"].get("environment",{})
for key in ("AIOPS_ADMIN_TOKEN","AIOPS_INTERNAL_TOKEN","CORE_URL","GLPI_API_URL","GLPI_APP_TOKEN","GLPI_USER_TOKEN"):
    if str(actual.get(key,"")) != os.environ[key]:
        raise SystemExit("Refusing: Compose variable mismatch for "+key)
print("COMPOSE_ENVIRONMENT_MATCH=YES")
PY_ENV
rm -f "$BACKUP/merged.json"
echo "Previous image recorded; deploying portal service only."
docker compose -p "$PROJECT" "${ARGS[@]}" -f "$BACKUP/overlay.json" up -d --no-deps --no-build "$SERVICE"
echo "CUTOVER_COMPLETE — verify /health and /explorer/prometheus from trusted administration network"
echo "BACKUP_DIR=$BACKUP"
echo "Sensitive Compose overlays removed on exit; rollback requires approved regeneration."
echo "ROLLBACK_IMAGE=$CURRENT"
echo "No run execution, GLPI ticket update or HITL action requested."
