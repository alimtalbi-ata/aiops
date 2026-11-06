#!/usr/bin/env bash
set -uo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
NAME=aiops2-fs1100-history-network-probe
PORT=17900
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "FS1100_MODE=TEMPORARY_CANDIDATE_NETWORK_AND_LISTENER_DIAGNOSTIC"
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "FS1100_ERROR=CANDIDATE_IMAGE_MISSING"; exit 2
fi
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FS1100_ERROR=TEMP_NAME_ALREADY_EXISTS"; exit 2
fi
PROD_BEFORE="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' 2>/dev/null)" || exit 2
echo "FS1100_PRODUCTION_IMAGE_BEFORE=$PROD_BEFORE"
if [[ "$PROD_BEFORE" != "aiops2-portal:fs1073-csp-candidate" ]]; then
  echo "FS1100_ERROR=UNEXPECTED_PRODUCTION_IMAGE"; exit 2
fi
CONTROL_SUBNET="$(docker network inspect aiops2-rebuild-control --format '{{(index .IPAM.Config 0).Subnet}}' 2>/dev/null)" || exit 2
docker network inspect aiops2-rebuild-integration >/dev/null 2>&1 || exit 2
echo "FS1100_CONTROL_SUBNET=$CONTROL_SUBNET"

docker run -d --name "$NAME" --restart no --network aiops2-rebuild-control \
  --publish "127.0.0.1:${PORT}:777/tcp" \
  -e AIOPS_INTERNAL_TOKEN=fs1100-ephemeral-only \
  -e EXPLORER_ENABLED=1 -e "EXPLORER_ALLOWED_CIDRS=$CONTROL_SUBNET" \
  "$IMAGE" >/dev/null
RUN_RC=$?
if [[ "$RUN_RC" -ne 0 ]]; then echo "FS1100_DOCKER_RUN=FAIL"; exit 1; fi
docker network connect aiops2-rebuild-integration "$NAME" || { echo "FS1100_INTEGRATION_ATTACH=FAIL"; exit 1; }

echo "FS1100_STATE=$(docker inspect "$NAME" --format '{{.State.Status}}')"
echo "FS1100_PATH=$(docker inspect "$NAME" --format '{{.Path}}')"
echo "FS1100_ARGS=$(docker inspect "$NAME" --format '{{json .Args}}')"
echo "FS1100_EXPOSED_PORTS=$(docker inspect "$NAME" --format '{{json .Config.ExposedPorts}}')"
echo "FS1100_PORT_BINDINGS=$(docker inspect "$NAME" --format '{{json .HostConfig.PortBindings}}')"
echo "FS1100_NETWORK_PORTS=$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
echo "FS1100_PUBLISHED_PORT=$(docker port "$NAME" 777/tcp 2>&1 || true)"

INTERNAL=NO
for i in $(seq 1 35); do
  if docker exec "$NAME" python -c 'import socket,sys;s=socket.create_connection(("127.0.0.1",777),timeout=1);s.close()' >/dev/null 2>&1; then
    INTERNAL=YES; break
  fi
  sleep 1
done
echo "FS1100_INTERNAL_TCP=$INTERNAL"
if [[ "$INTERNAL" == YES ]]; then
  docker exec "$NAME" python -c 'import urllib.request; r=urllib.request.urlopen("http://127.0.0.1:777/health",timeout=4); print("FS1100_INTERNAL_HTTP="+str(r.status))' 2>&1 || echo "FS1100_INTERNAL_HTTP=REQUEST_FAILED"
else
  echo "FS1100_INTERNAL_HTTP=NOT_TESTED"
fi

HOST=NO
for i in $(seq 1 12); do
  CODE="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:${PORT}/health" 2>/dev/null || true)"
  if [[ "$CODE" != "000" && -n "$CODE" ]]; then HOST=YES; echo "FS1100_HOST_HTTP=$CODE"; break; fi
  sleep 1
done
echo "FS1100_HOST_REACHABLE=$HOST"
echo "FS1100_LOG_TAIL_BEGIN"
docker logs --tail 30 "$NAME" 2>&1
echo "FS1100_LOG_TAIL_END"
PROD_AFTER="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}' 2>/dev/null)"
echo "FS1100_PRODUCTION_IMAGE_AFTER=$PROD_AFTER"
if [[ "$PROD_AFTER" != "$PROD_BEFORE" ]]; then echo "FS1100_ERROR=PRODUCTION_IMAGE_CHANGED"; exit 3; fi
if [[ "$INTERNAL" == YES && "$HOST" == YES ]]; then
  echo "FS1100_RESULT=PASS"
else
  echo "FS1100_RESULT=DIAGNOSTIC_COMPLETE"
fi
echo "FS1100_PRODUCTION_MUTATION=NONE"
