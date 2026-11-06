#!/usr/bin/env bash
set -euo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
PROD=aiops2-rebuild-portal
PORT_BASE=17905
NETWORKS=(bridge aiops2-rebuild-control aiops2-rebuild-integration aiops2-rebuild-public aiops2-rebuild-observability)
NAMES=()

cleanup() {
  for name in "${NAMES[@]}"; do
    docker rm -f "$name" >/dev/null 2>&1 || true
  done
}
trap cleanup EXIT

echo "FS1104_MODE=READ_ONLY_NETWORK_CONFIG_AND_EPHEMERAL_PUBLISH_MATRIX"
PROD_IMAGE_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1104_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE_BEFORE"
[[ "$PROD_IMAGE_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]] || {
  echo "FS1104_ERROR=UNEXPECTED_PRODUCTION_IMAGE"
  exit 2
}

echo "FS1104_NETWORK_CONFIG_BEGIN"
for network in "${NETWORKS[@]}"; do
  if ! docker network inspect "$network" >/dev/null 2>&1; then
    echo "FS1104_NETWORK=$network STATE=ABSENT"
    continue
  fi
  docker network inspect "$network" --format 'FS1104_NETWORK={{.Name}} DRIVER={{.Driver}} INTERNAL={{.Internal}} ATTACHABLE={{.Attachable}} INGRESS={{.Ingress}} ENABLE_IPV4={{.EnableIPv4}} IPAM={{json .IPAM.Config}} OPTIONS={{json .Options}}'
done
echo "FS1104_NETWORK_CONFIG_END"

echo "FS1104_ROOTLESS_PORT_DRIVER_BEGIN"
ps -eo pid,ppid,args | grep -E '[r]ootlesskit|[s]lirp4netns|[d]ocker-proxy' || true
echo "FS1104_ROOTLESS_PORT_DRIVER_END"

index=0
for network in "${NETWORKS[@]}"; do
  docker network inspect "$network" >/dev/null 2>&1 || continue
  port=$((PORT_BASE + index))
  name="aiops2-fs1104-${network##*-}"
  # Use a unique name even if network names share the same suffix.
  name="aiops2-fs1104-$index"
  index=$((index + 1))
  NAMES+=("$name")

  if docker container inspect "$name" >/dev/null 2>&1; then
    echo "FS1104_ERROR=TEMP_NAME_ALREADY_EXISTS name=$name"
    exit 2
  fi
  if ss -ltnH "sport = :$port" 2>/dev/null | grep -q .; then
    echo "FS1104_ERROR=HOST_PORT_ALREADY_LISTENING port=$port"
    exit 2
  fi

  echo "FS1104_PROBE_BEGIN network=$network name=$name port=$port"
  docker run -d --name "$name" --restart no --network "$network" \
    --publish "127.0.0.1:${port}:777/tcp" \
    -e AIOPS_INTERNAL_TOKEN=fs1104-ephemeral-only \
    -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 \
    "$IMAGE" >/dev/null

  internal=NO
  for attempt in $(seq 1 15); do
    if docker exec "$name" python -c 'import socket;s=socket.create_connection(("127.0.0.1",777),timeout=1);s.close()' >/dev/null 2>&1; then
      internal=YES
      break
    fi
    sleep 1
  done

  docker inspect "$name" --format 'FS1104_CONTAINER={{.Name}} STATE={{.State.Status}} HOSTCONFIG={{json .HostConfig.PortBindings}} RUNTIME={{json .NetworkSettings.Ports}} NETWORKS={{json .NetworkSettings.Networks}}'
  echo "FS1104_INTERNAL_TCP=$internal"
  echo "FS1104_DOCKER_PORT=$(docker port "$name" 777/tcp 2>&1 || true)"
  ps -eo pid,ppid,args | grep -E "[d]ocker-proxy.*$port" || true
  curl -sS -o /dev/null -w "FS1104_HOST_HTTP network=$network code=%{http_code}\n" --max-time 3 "http://127.0.0.1:$port/health" 2>/dev/null || true
  echo "FS1104_LOG_TAIL_BEGIN network=$network"
  docker logs --tail 6 "$name" 2>&1
  echo "FS1104_LOG_TAIL_END network=$network"
  echo "FS1104_PROBE_END network=$network"
done

PROD_IMAGE_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1104_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE_BEFORE" ]] || {
  echo "FS1104_ERROR=PRODUCTION_IMAGE_CHANGED"
  exit 3
}
echo "FS1104_RESULT=DIAGNOSTIC_COMPLETE"
echo "FS1104_PRODUCTION_MUTATION=NONE"
