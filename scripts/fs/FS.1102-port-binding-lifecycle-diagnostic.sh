#!/usr/bin/env bash
set -uo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
NAME=aiops2-fs1102-publish-lifecycle
PORT=17902
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "FS1102_MODE=EPHEMERAL_PORT_BINDING_LIFECYCLE_DIAGNOSTIC"
PROD_BEFORE="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' 2>/dev/null)" || exit 2
echo "FS1102_PRODUCTION_IMAGE_BEFORE=$PROD_BEFORE"
[[ "$PROD_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]] || { echo "FS1102_ERROR=UNEXPECTED_PRODUCTION_IMAGE"; exit 2; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "FS1102_ERROR=CANDIDATE_IMAGE_MISSING"; exit 2; }
docker network inspect aiops2-rebuild-control >/dev/null 2>&1 || exit 2
docker network inspect aiops2-rebuild-integration >/dev/null 2>&1 || exit 2
if docker container inspect "$NAME" >/dev/null 2>&1; then echo "FS1102_ERROR=TEMP_NAME_ALREADY_EXISTS"; exit 2; fi

SUBNET="$(docker network inspect aiops2-rebuild-control --format '{{(index .IPAM.Config 0).Subnet}}')"
echo "FS1102_CONTROL_SUBNET=$SUBNET"

snapshot(){
  local phase="$1"
  echo "FS1102_PHASE=$phase"
  docker inspect "$NAME" --format 'STATE={{.State.Status}} IP={{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}} HOSTCONFIG={{json .HostConfig.PortBindings}} RUNTIME={{json .NetworkSettings.Ports}} NETWORKS={{json .NetworkSettings.Networks}}'
  echo "FS1102_DOCKER_PORT=$(docker port "$NAME" 777/tcp 2>&1 || true)"
  ps -eo pid,ppid,args | grep -E "[d]ocker-proxy.*17902" || true
  curl -sS -o /dev/null -w "FS1102_HOST_HTTP=$phase:%{http_code}\n" --max-time 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null || true
}

docker run -d --name "$NAME" --restart no --network aiops2-rebuild-control \
  --publish "127.0.0.1:${PORT}:777/tcp" \
  -e AIOPS_INTERNAL_TOKEN=fs1102-ephemeral-only \
  -e EXPLORER_ENABLED=1 -e "EXPLORER_ALLOWED_CIDRS=$SUBNET" \
  "$IMAGE" >/dev/null || { echo "FS1102_DOCKER_RUN=FAIL"; exit 1; }

for i in $(seq 1 20); do
  if docker exec "$NAME" python -c 'import socket;s=socket.create_connection(("127.0.0.1",777),timeout=1);s.close()' >/dev/null 2>&1; then break; fi
  sleep 1
done
snapshot BEFORE_SECOND_NETWORK_CONNECT

echo "FS1102_CONNECT_INTEGRATION_BEGIN"
docker network connect aiops2-rebuild-integration "$NAME"
CONNECT_RC=$?
echo "FS1102_CONNECT_INTEGRATION_RC=$CONNECT_RC"
snapshot AFTER_SECOND_NETWORK_CONNECT

echo "FS1102_DAEMON_EVENTS_BEGIN"
docker events --since 3m --until "$(date --iso-8601=seconds)" --filter "container=$NAME" --format '{{.Time}} {{.Action}} {{json .Actor.Attributes}}' 2>&1 | tail -30 || true
echo "FS1102_DAEMON_EVENTS_END"
echo "FS1102_CONTAINER_LOGS_BEGIN"
docker logs --tail 20 "$NAME" 2>&1
echo "FS1102_CONTAINER_LOGS_END"

PROD_AFTER="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' 2>/dev/null)"
echo "FS1102_PRODUCTION_IMAGE_AFTER=$PROD_AFTER"
[[ "$PROD_AFTER" == "$PROD_BEFORE" ]] || { echo "FS1102_ERROR=PRODUCTION_IMAGE_CHANGED"; exit 3; }
echo "FS1102_RESULT=DIAGNOSTIC_COMPLETE"
echo "FS1102_PRODUCTION_MUTATION=NONE"
