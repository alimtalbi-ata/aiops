#!/usr/bin/env bash
set -euo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
PROD=aiops2-rebuild-portal
NAME=aiops2-fs1106-publish-first-lifecycle
PORT=17912
NETWORKS=(aiops2-rebuild-control aiops2-rebuild-integration aiops2-rebuild-observability)
INITIAL_NETWORK=aiops2-rebuild-public

cleanup() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "FS1106_MODE=EPHEMERAL_EXTERNAL_FIRST_THEN_INTERNAL_NETWORKS"
PROD_IMAGE_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1106_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE_BEFORE"
[[ "$PROD_IMAGE_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]] || {
  echo "FS1106_ERROR=UNEXPECTED_PRODUCTION_IMAGE"
  exit 2
}

if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FS1106_ERROR=TEMP_CONTAINER_ALREADY_EXISTS"
  exit 2
fi
if ss -ltnH "sport = :$PORT" 2>/dev/null | grep -q .; then
  echo "FS1106_ERROR=HOST_PORT_ALREADY_LISTENING port=$PORT"
  exit 2
fi

echo "FS1106_CREATE_BEGIN initial_network=$INITIAL_NETWORK"
docker run -d --name "$NAME" --restart no \
  --network "$INITIAL_NETWORK" \
  --publish "127.0.0.1:${PORT}:777/tcp" \
  -e AIOPS_INTERNAL_TOKEN=fs1106-ephemeral-only \
  -e EXPLORER_ENABLED=1 \
  -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 \
  "$IMAGE" >/dev/null

check_stage() {
  local stage="$1"
  local inspect runtime docker_port host_code
  inspect="$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
  runtime="$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
  docker_port="$(docker port "$NAME" 777/tcp 2>&1 || true)"
  host_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$PORT/health" 2>/dev/null || true)"
  echo "FS1106_STAGE=$stage RUNTIME=$runtime DOCKER_PORT=$docker_port HOST_HTTP=$host_code"
  [[ "$runtime" == *"17912"* ]] || {
    echo "FS1106_ERROR=RUNTIME_BINDING_LOST stage=$stage"
    return 1
  }
  [[ "$host_code" == "200" ]] || {
    echo "FS1106_ERROR=HOST_HTTP_NOT_200 stage=$stage"
    return 1
  }
}

for attempt in $(seq 1 20); do
  if docker exec "$NAME" python -c 'import urllib.request;urllib.request.urlopen("http://127.0.0.1:777/health",timeout=1)' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

check_stage "INITIAL_EXTERNAL_NETWORK"

for network in "${NETWORKS[@]}"; do
  echo "FS1106_CONNECT_BEGIN network=$network"
  docker network connect "$network" "$NAME"
  check_stage "AFTER_$network"
done

echo "FS1106_FINAL_NETWORKS=$(docker inspect "$NAME" --format '{{json .NetworkSettings.Networks}}')"
echo "FS1106_CONTAINER_LOG_TAIL_BEGIN"
docker logs --tail 20 "$NAME" 2>&1 || true
echo "FS1106_CONTAINER_LOG_TAIL_END"

PROD_IMAGE_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1106_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE_BEFORE" ]] || {
  echo "FS1106_ERROR=PRODUCTION_IMAGE_CHANGED"
  exit 3
}
echo "FS1106_RESULT=PASS"
echo "FS1106_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1106_PRODUCTION_MUTATION=NONE"
