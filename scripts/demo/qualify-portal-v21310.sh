#!/usr/bin/env bash
# Read-only deployment verification. Never recreates containers or changes networks.
set -u -o pipefail
cd /home/aiops/aiops-v28-demo || exit 2
FILES=(-f compose.yml -f compose.demo-local.yml -f compose.llm-test.yml -f compose.dgx-network.yml -f /home/aiops/portal-v21310.override.yml)
URL="http://10.79.94.202:17777"
CID=$(docker compose "${FILES[@]}" --profile '*' ps -q aiops2-portal 2>/dev/null)
if [[ -z "$CID" ]]; then echo "PORTAL_CONTAINER=NOT_FOUND"; exit 2; fi
ACTIVE=$(docker inspect "$CID" --format '{{.Image}}') || exit 2
TARGET=$(docker image inspect aiops2-portal:v21310 --format '{{.Id}}') || exit 2
echo "CONTAINER_ID=$CID"
echo "ACTIVE_IMAGE=$ACTIVE"
echo "TARGET_IMAGE=$TARGET"
if [[ "$ACTIVE" != "$TARGET" ]]; then echo "IMAGE_MATCH=FAIL"; exit 1; fi
echo "IMAGE_MATCH=PASS"
declare -A EXPECT=(["/health"]=200 ["/"]=200 ["/demo-studio"]=200 ["/demo/"]=200 ["/demo/star"]=200 ["/demo/view/AIOPS-REAL-STACK-REPLAY.html"]=403)
fail=0
for path in /health / /demo-studio /demo/ /demo/star /demo/view/AIOPS-REAL-STACK-REPLAY.html; do
  status=$(curl -sS --max-time 8 -o /dev/null -w '%{http_code}' "$URL$path" 2>/dev/null) || status=000
  printf '%-54s HTTP %s expected %s\n' "$path" "$status" "${EXPECT[$path]}"
  [[ "$status" == "${EXPECT[$path]}" ]] || fail=1
done
if [[ "$fail" == 0 ]]; then echo "AIOPS_V21310_POST_DEPLOY=PASS"; else echo "AIOPS_V21310_POST_DEPLOY=FAIL"; fi
exit "$fail"
