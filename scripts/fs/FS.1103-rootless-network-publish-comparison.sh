#!/usr/bin/env bash
set -euo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
PROD=aiops2-rebuild-portal
NAME_CONTROL=aiops2-fs1103-control
NAME_DEFAULT=aiops2-fs1103-default
PORT_CONTROL=17903
PORT_DEFAULT=17904

cleanup() {
  docker rm -f "$NAME_CONTROL" "$NAME_DEFAULT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "FS1103_MODE=EPHEMERAL_ROOTLESS_NETWORK_PUBLISH_COMPARISON"
PROD_IMAGE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1103_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE"
[[ "$PROD_IMAGE" == "aiops2-portal:fs1073-csp-candidate" ]] || { echo "FS1103_ERROR=UNEXPECTED_PRODUCTION_IMAGE"; exit 2; }

for name in "$NAME_CONTROL" "$NAME_DEFAULT"; do
  if docker container inspect "$name" >/dev/null 2>&1; then
    echo "FS1103_ERROR=TEMP_NAME_ALREADY_EXISTS name=$name"
    exit 2
  fi
done

echo "FS1103_DOCKER_INFO_BEGIN"
docker info --format 'ROOT={{.DockerRootDir}} SECURITY={{json .SecurityOptions}} DRIVER={{.Driver}}'
echo "FS1103_DOCKER_INFO_END"

echo "FS1103_PRODUCTION_PORT_STATE_BEGIN"
docker inspect "$PROD" --format 'IMAGE={{.Config.Image}} STATE={{.State.Status}} HOSTCONFIG={{json .HostConfig.PortBindings}} RUNTIME={{json .NetworkSettings.Ports}} NETWORKS={{json .NetworkSettings.Networks}}'
echo "FS1103_PRODUCTION_PORT_STATE_END"

run_probe() {
  local name="$1" port="$2" network="$3"
  echo "FS1103_START name=$name network=$network host_port=$port"
  docker run -d --name "$name" --restart no --network "$network" \
    --publish "127.0.0.1:${port}:777/tcp" \
    -e AIOPS_INTERNAL_TOKEN=fs1103-ephemeral-only \
    -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 \
    "$IMAGE" >/dev/null

  for i in $(seq 1 20); do
    if docker exec "$name" python -c 'import socket;s=socket.create_connection(("127.0.0.1",777),timeout=1);s.close()' >/dev/null 2>&1; then break; fi
    sleep 1
  done

  docker inspect "$name" --format 'FS1103_INSPECT name={{.Name}} STATE={{.State.Status}} HOSTCONFIG={{json .HostConfig.PortBindings}} RUNTIME={{json .NetworkSettings.Ports}} NETWORKS={{json .NetworkSettings.Networks}}'
  echo "FS1103_DOCKER_PORT name=$name value=$(docker port "$name" 777/tcp 2>&1 || true)"
  ps -eo pid,ppid,args | grep -E "[d]ocker-proxy.*${port}" || true
  curl -sS -o /dev/null -w "FS1103_HOST_HTTP name=$name code=%{http_code}\n" --max-time 3 "http://127.0.0.1:${port}/health" 2>/dev/null || true
  echo "FS1103_LOGS name=$name"
  docker logs --tail 8 "$name" 2>&1
}

run_probe "$NAME_DEFAULT" "$PORT_DEFAULT" bridge
run_probe "$NAME_CONTROL" "$PORT_CONTROL" aiops2-rebuild-control

PROD_IMAGE_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1103_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE" ]] || { echo "FS1103_ERROR=PRODUCTION_IMAGE_CHANGED"; exit 3; }
echo "FS1103_RESULT=DIAGNOSTIC_COMPLETE"
echo "FS1103_PRODUCTION_MUTATION=NONE"
