#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
CONTAINER="${AIOPS_PORTAL_CONTAINER:-aiops2-rebuild-portal}"
TARGET_PORT=7770
SERVICE="aiops2-portal"
fail(){ echo "FAIL|$1"; exit 1; }
docker inspect "$CONTAINER" >/dev/null 2>&1 || fail "existing_portal_missing"
PROJECT="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$CONTAINER")"
WORKDIR="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.working_dir" }}' "$CONTAINER")"
CONFIGS="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' "$CONTAINER")"
OLD_PORT="$(docker inspect -f '{{(index (index .NetworkSettings.Ports "777/tcp") 0).HostPort}}' "$CONTAINER")"
IMAGE_BEFORE="$(docker inspect -f '{{.Image}}' "$CONTAINER")"
[[ -n "$PROJECT" ]] || fail "compose_project_label_missing"
SERVICE="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.service" }}' "$CONTAINER")"
[[ "$SERVICE" == "aiops2-portal" ]] || fail "unexpected_compose_service"
[[ -n "$WORKDIR" && -d "$WORKDIR" ]] || fail "compose_workdir_missing"
[[ -n "$CONFIGS" ]] || fail "compose_config_label_missing"
[[ "$OLD_PORT" =~ ^[0-9]+$ ]] || fail "current_port_unknown"
[[ "$OLD_PORT" != "$TARGET_PORT" ]] || { echo "PORTAL_ALREADY_ON_7770=PASS"; exit 0; }
IFS=',' read -r -a FILES <<< "$CONFIGS"
COMPOSE_ARGS=()
for file in "${FILES[@]}"; do
  [[ -f "$file" ]] || fail "compose_file_missing"
  COMPOSE_ARGS+=(-f "$file")
done
if ss -ltnH "sport = :$TARGET_PORT" | grep -q .; then fail "target_port_7770_in_use"; fi
if docker ps --format '{{.Names}} {{.Ports}}' | grep -E "0\.0\.0\.0:$TARGET_PORT->|127\.0\.0\.1:$TARGET_PORT->|\[::\]:$TARGET_PORT->" >/dev/null; then fail "target_port_7770_published_by_another_container"; fi
docker inspect "$CONTAINER" > /tmp/aiops2-portal-7770-before.json
python3 - /tmp/aiops2-portal-7770-before.json <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))[0]
assert x["State"]["Running"], "portal_not_running"
assert x["Config"]["Labels"].get("com.docker.compose.service") == "aiops2-portal", "unexpected_compose_service"
PY
echo "===== SINGLE PORTAL CUTOVER ====="
echo "PROJECT=$PROJECT"
echo "SERVICE=$SERVICE"
echo "OLD_PORT=$OLD_PORT"
echo "TARGET_PORT=$TARGET_PORT"
echo "BUILD=false"
echo "OTHER_SERVICES_TOUCHED=false"
rollback(){
  rc=$?
  if [[ "$rc" -ne 0 ]]; then
    set +e
    echo "CUTOVER_FAILED_ROLLBACK_BEGIN"
    AIOPS_PORTAL_HOST_PORT="$OLD_PORT" docker compose --project-directory "$WORKDIR" -p "$PROJECT" "${COMPOSE_ARGS[@]}" up -d --no-deps --no-build "$SERVICE"
    echo "ROLLBACK_EXIT=$?"
    echo "ROLLBACK_TARGET_PORT=$OLD_PORT"
  fi
}
trap rollback EXIT
AIOPS_PORTAL_HOST_PORT="$TARGET_PORT" docker compose --project-directory "$WORKDIR" -p "$PROJECT" "${COMPOSE_ARGS[@]}" up -d --no-deps --no-build "$SERVICE"
IMAGE_AFTER="$(docker inspect -f '{{.Image}}' "$CONTAINER")"
[[ "$IMAGE_AFTER" == "$IMAGE_BEFORE" ]] || fail "image_changed"
docker inspect "$CONTAINER" > /tmp/aiops2-portal-7770-after.json
python3 - /tmp/aiops2-portal-7770-before.json /tmp/aiops2-portal-7770-after.json <<'PY'
import json,sys
a=json.load(open(sys.argv[1]))[0]
b=json.load(open(sys.argv[2]))[0]
def env(x):
    return sorted(v for v in x["Config"]["Env"] if not v.startswith("AIOPS_PORTAL_HOST_PORT="))
assert env(a)==env(b), "environment_changed_outside_port"
def mounts(x):
    return sorted((m["Type"],m["Source"],m["Destination"],m["RW"]) for m in x["Mounts"])
assert mounts(a)==mounts(b), "mounts_changed"
assert sorted(a["NetworkSettings"]["Networks"])==sorted(b["NetworkSettings"]["Networks"]), "networks_changed"
assert b["State"]["Running"], "portal_not_running"
assert b["Config"]["Labels"].get("com.docker.compose.project")=="aiops2-rebuild"
assert b["Config"]["Labels"].get("com.docker.compose.service")=="aiops2-portal"
PY
for i in $(seq 1 30); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$TARGET_PORT/health" >/dev/null 2>&1; then break; fi
  sleep 1
done
curl -fsS --max-time 5 "http://127.0.0.1:$TARGET_PORT/health" >/dev/null
curl -fsS --max-time 5 "http://127.0.0.1:$TARGET_PORT/" -o /dev/null
docker port "$CONTAINER" 777/tcp | grep -q ":$TARGET_PORT$" || fail "published_port_mismatch"
trap - EXIT
echo "IMAGE_UNCHANGED=PASS"
echo "ENV_UNCHANGED_EXCEPT_PORT=PASS"
echo "MOUNTS_UNCHANGED=PASS"
echo "NETWORKS_UNCHANGED=PASS"
echo "PORTAL_HEALTH=PASS"
echo "PORTAL_UI_HTTP=200"
echo "OLD_PORT=$OLD_PORT"
echo "NEW_PORT=$TARGET_PORT"
echo "POC_PORTALS_UNTOUCHED=true"
echo "PORTAL_URL=http://$(hostname -I | awk '{print $1}'):$TARGET_PORT/"
