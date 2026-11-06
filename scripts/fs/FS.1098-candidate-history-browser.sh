#!/usr/bin/env bash
set -euo pipefail
IMAGE=aiops2-portal:fs1097-history-chart-candidate
NAME=aiops2-fs1098-history-browser-temp
PORT=17898
ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
PLAYWRIGHT_PY=/home/aiops/.local/share/aiops-playwright-venv/bin/python
cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "FS1098_MODE=TEMPORARY_CANDIDATE_REAL_CHROMIUM_HISTORY_MATRIX"
docker image inspect "$IMAGE" >/dev/null
docker network inspect aiops2-rebuild-control >/dev/null
test -x "$PLAYWRIGHT_PY"
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FS1098_ERROR=TEMP_NAME_ALREADY_EXISTS"; exit 1
fi
PROD_IMAGE="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')"
echo "FS1098_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE"
if [[ "$PROD_IMAGE" != "aiops2-portal:fs1073-csp-candidate" ]]; then
  echo "FS1098_ERROR=UNEXPECTED_PRODUCTION_IMAGE"; exit 2
fi
SUBNET="$(docker network inspect aiops2-rebuild-control --format '{{(index .IPAM.Config 0).Subnet}}')"
test -n "$SUBNET"
docker run -d --name "$NAME" --restart no --network aiops2-rebuild-control \
  -p "127.0.0.1:${PORT}:777" \
  -e AIOPS_INTERNAL_TOKEN=fs1098-ephemeral-test-only \
  -e EXPLORER_ENABLED=1 -e "EXPLORER_ALLOWED_CIDRS=$SUBNET" \
  "$IMAGE" >/dev/null
READY=NO
for i in $(seq 1 40); do
  if curl -fsS --max-time 2 "http://127.0.0.1:${PORT}/explorer/visual" -o /dev/null; then READY=YES; break; fi
  sleep 1
done
echo "FS1098_HTTP_READY=$READY"
if [[ "$READY" != YES ]]; then
  docker logs --tail 35 "$NAME" 2>&1 | sed -E 's/(token|secret|password)=([^ ]+)/\1=[REDACTED]/Ig'
  exit 1
fi
"$PLAYWRIGHT_PY" "$ROOT/scripts/fs/fs1098_browser_history.py"
PROD_IMAGE_AFTER="$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')"
echo "FS1098_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE" ]]
echo "FS1098_TEMP_CONTAINER_CLEANUP=TRAP_ARMED"
echo "FS1098_PRODUCTION_MUTATION=NONE"
