#!/usr/bin/env bash
set -euo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
PROD=aiops2-rebuild-portal
NET_EXTERNAL=aiops2-fs1105-external
NET_INTERNAL=aiops2-fs1105-internal
NAME_EXTERNAL=aiops2-fs1105-external
NAME_INTERNAL=aiops2-fs1105-internal
PORT_EXTERNAL=17910
PORT_INTERNAL=17911

cleanup() {
  docker rm -f "$NAME_EXTERNAL" "$NAME_INTERNAL" >/dev/null 2>&1 || true
  docker network rm "$NET_EXTERNAL" "$NET_INTERNAL" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "FS1105_MODE=EPHEMERAL_INTERNAL_FLAG_CONTROLLED_AB_TEST"
PROD_IMAGE_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1105_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE_BEFORE"
[[ "$PROD_IMAGE_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]] || {
  echo "FS1105_ERROR=UNEXPECTED_PRODUCTION_IMAGE"
  exit 2
}

for name in "$NET_EXTERNAL" "$NET_INTERNAL" "$NAME_EXTERNAL" "$NAME_INTERNAL"; do
  if docker network inspect "$name" >/dev/null 2>&1 || docker container inspect "$name" >/dev/null 2>&1; then
    echo "FS1105_ERROR=TEMP_NAME_ALREADY_EXISTS name=$name"
    exit 2
  fi
done

for port in "$PORT_EXTERNAL" "$PORT_INTERNAL"; do
  if ss -ltnH "sport = :$port" 2>/dev/null | grep -q .; then
    echo "FS1105_ERROR=HOST_PORT_ALREADY_LISTENING port=$port"
    exit 2
  fi
done

echo "FS1105_CREATE_NETWORKS_BEGIN"
docker network create --driver bridge "$NET_EXTERNAL" >/dev/null
docker network create --driver bridge --internal "$NET_INTERNAL" >/dev/null
docker network inspect "$NET_EXTERNAL" "$NET_INTERNAL" --format 'FS1105_NETWORK={{.Name}} INTERNAL={{.Internal}} DRIVER={{.Driver}} IPAM={{json .IPAM.Config}} OPTIONS={{json .Options}}'
echo "FS1105_CREATE_NETWORKS_END"

probe() {
  local network="$1" name="$2" port="$3"
  echo "FS1105_PROBE_BEGIN network=$network port=$port"
  docker run -d --name "$name" --restart no --network "$network" \
    --publish "127.0.0.1:${port}:777/tcp" \
    -e AIOPS_INTERNAL_TOKEN=fs1105-ephemeral-only \
    -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 \
    "$IMAGE" >/dev/null

  internal_tcp=NO
  for attempt in $(seq 1 20); do
    if docker exec "$name" python -c 'import socket;s=socket.create_connection(("127.0.0.1",777),timeout=1);s.close()' >/dev/null 2>&1; then
      internal_tcp=YES
      break
    fi
    sleep 1
  done

  docker inspect "$name" --format 'FS1105_CONTAINER={{.Name}} STATE={{.State.Status}} HOSTCONFIG={{json .HostConfig.PortBindings}} RUNTIME={{json .NetworkSettings.Ports}} NETWORKS={{json .NetworkSettings.Networks}}'
  echo "FS1105_INTERNAL_TCP=$internal_tcp"
  echo "FS1105_DOCKER_PORT=$(docker port "$name" 777/tcp 2>&1 || true)"
  ps -eo pid,ppid,args | grep -E "[d]ocker-proxy.*$port" || true
  curl -sS -o /dev/null -w "FS1105_HOST_HTTP network=$network code=%{http_code}\n" --max-time 3 "http://127.0.0.1:$port/health" 2>/dev/null || true
  echo "FS1105_PROBE_END network=$network"
}

probe "$NET_EXTERNAL" "$NAME_EXTERNAL" "$PORT_EXTERNAL"
probe "$NET_INTERNAL" "$NAME_INTERNAL" "$PORT_INTERNAL"

PROD_IMAGE_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1105_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE_BEFORE" ]] || {
  echo "FS1105_ERROR=PRODUCTION_IMAGE_CHANGED"
  exit 3
}
echo "FS1105_RESULT=DIAGNOSTIC_COMPLETE"
echo "FS1105_PRODUCTION_MUTATION=NONE"
