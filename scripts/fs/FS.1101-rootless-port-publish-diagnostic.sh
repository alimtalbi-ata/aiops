#!/usr/bin/env bash
set -uo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
NAME=aiops2-fs1101-rootless-publish-diag
PORT=17901
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "FS1101_MODE=READ_ONLY_ROOTLESS_PUBLISH_DIAGNOSTIC_WITH_EPHEMERAL_CONTAINER"
PROD_BEFORE="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' 2>/dev/null)" || exit 2
echo "FS1101_PRODUCTION_IMAGE_BEFORE=$PROD_BEFORE"
[[ "$PROD_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]] || { echo "FS1101_ERROR=UNEXPECTED_PRODUCTION_IMAGE"; exit 2; }
docker image inspect "$IMAGE" >/dev/null 2>&1 || { echo "FS1101_ERROR=CANDIDATE_IMAGE_MISSING"; exit 2; }
docker network inspect aiops2-rebuild-control >/dev/null 2>&1 || exit 2
docker network inspect aiops2-rebuild-integration >/dev/null 2>&1 || exit 2
if docker container inspect "$NAME" >/dev/null 2>&1; then echo "FS1101_ERROR=TEMP_NAME_ALREADY_EXISTS"; exit 2; fi

echo "FS1101_DOCKER_INFO_BEGIN"
docker info --format 'ROOTLESS_SECURITY={{json .SecurityOptions}} DRIVER={{.Driver}} DOCKER_ROOT={{.DockerRootDir}} SERVER={{.ServerVersion}}'
echo "FS1101_DOCKER_INFO_END"
echo "FS1101_CONTEXT=$(docker context show 2>/dev/null || true)"
echo "FS1101_NETWORK_DRIVER=$(docker network inspect aiops2-rebuild-control --format '{{.Driver}}')"
echo "FS1101_NETWORK_OPTIONS=$(docker network inspect aiops2-rebuild-control --format '{{json .Options}}')"
echo "FS1101_ROOTLESSKIT_PROCESSES_BEGIN"
ps -eo pid,ppid,args | grep -E '[r]ootlesskit|[s]lirp4netns|[d]ockerd|[d]ocker-proxy' | head -30 || true
echo "FS1101_ROOTLESSKIT_PROCESSES_END"

SUBNET="$(docker network inspect aiops2-rebuild-control --format '{{(index .IPAM.Config 0).Subnet}}')"
docker run -d --name "$NAME" --restart no --network aiops2-rebuild-control \
  --publish "127.0.0.1:${PORT}:777/tcp" \
  -e AIOPS_INTERNAL_TOKEN=fs1101-ephemeral-only \
  -e EXPLORER_ENABLED=1 -e "EXPLORER_ALLOWED_CIDRS=$SUBNET" \
  "$IMAGE" >/dev/null || { echo "FS1101_DOCKER_RUN=FAIL"; exit 1; }
docker network connect aiops2-rebuild-integration "$NAME" || { echo "FS1101_INTEGRATION_ATTACH=FAIL"; exit 1; }
sleep 2

echo "FS1101_CONTAINER_STATE=$(docker inspect "$NAME" --format '{{.State.Status}}')"
echo "FS1101_HOSTCONFIG_BINDINGS=$(docker inspect "$NAME" --format '{{json .HostConfig.PortBindings}}')"
echo "FS1101_RUNTIME_PORTS=$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
echo "FS1101_DOCKER_PORT=$(docker port "$NAME" 777/tcp 2>&1 || true)"
echo "FS1101_HOST_LISTENER_BEGIN"
ss -ltnp 2>&1 | grep -E "127\\.0\\.0\\.1:${PORT}([[:space:]]|$)|:${PORT}([[:space:]]|$)" || true
echo "FS1101_HOST_LISTENER_END"
echo "FS1101_HOST_FORWARD_PROCESSES_BEGIN"
ps -eo pid,ppid,args | grep -E "[d]ocker-proxy|[r]ootlesskit|[s]lirp4netns" | head -30 || true
echo "FS1101_HOST_FORWARD_PROCESSES_END"

INTERNAL="$(docker exec "$NAME" python -c 'import urllib.request;print(urllib.request.urlopen("http://127.0.0.1:777/health",timeout=3).status)' 2>&1 || true)"
echo "FS1101_INTERNAL_HTTP=$INTERNAL"
HOST_CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:${PORT}/health" 2>/dev/null || true)"
echo "FS1101_HOST_HTTP=$HOST_CODE"
echo "FS1101_CONTAINER_LOG_TAIL_BEGIN"
docker logs --tail 15 "$NAME" 2>&1
echo "FS1101_CONTAINER_LOG_TAIL_END"
PROD_AFTER="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' 2>/dev/null)"
echo "FS1101_PRODUCTION_IMAGE_AFTER=$PROD_AFTER"
[[ "$PROD_AFTER" == "$PROD_BEFORE" ]] || { echo "FS1101_ERROR=PRODUCTION_IMAGE_CHANGED"; exit 3; }
echo "FS1101_RESULT=DIAGNOSTIC_COMPLETE"
echo "FS1101_PRODUCTION_MUTATION=NONE"
