#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
IMAGE=aiops2-portal:fs1097-history-chart-candidate
PROD=aiops2-rebuild-portal
NAME=aiops2-fs1107-history-full-candidate
PORT=17898
INITIAL_NETWORK=aiops2-rebuild-public
NETWORKS=(aiops2-rebuild-control aiops2-rebuild-integration aiops2-rebuild-observability)
PLAYWRIGHT_PY=/home/aiops/.local/share/aiops-playwright-venv/bin/python

# Never remove a container we did not create. In particular, a preflight
# collision must not delete the pre-existing candidate on EXIT.
CANDIDATE_ID=""
cleanup() {
  # A reused name is not proof of ownership. Only remove our exact container ID.
  if [[ -n "$CANDIDATE_ID" ]]; then
    local current_id
    current_id="$(docker inspect "$NAME" --format '{{.Id}}' 2>/dev/null)" || return 0
    if [[ "$current_id" == "$CANDIDATE_ID" ]]; then
      docker rm -f "$CANDIDATE_ID" >/dev/null 2>&1 || true
    else
      echo "FS1107_CLEANUP_SKIPPED=IDENTITY_CHANGED" >&2
    fi
  fi
}
trap cleanup EXIT

echo "FS1107_MODE=NONPRODUCTION_FULL_CANDIDATE_EXTERNAL_FIRST_BROWSER_MATRIX"
PROD_IMAGE_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1107_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE_BEFORE"
[[ "$PROD_IMAGE_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]] || {
  echo "FS1107_ERROR=UNEXPECTED_PRODUCTION_IMAGE"
  exit 2
}

for network in "$INITIAL_NETWORK" "${NETWORKS[@]}"; do
  docker network inspect "$network" >/dev/null
done
test -x "$PLAYWRIGHT_PY" || {
  echo "FS1107_ERROR=PLAYWRIGHT_PYTHON_NOT_FOUND"
  exit 2
}
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FS1107_ERROR=TEMP_NAME_ALREADY_EXISTS"
  exit 2
fi
if ss -ltnH "sport = :$PORT" 2>/dev/null | grep -q .; then
  echo "FS1107_ERROR=HOST_PORT_ALREADY_LISTENING port=$PORT"
  exit 2
fi

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "FS1107_CANDIDATE_IMAGE=BUILD_REQUIRED"
  bash "$ROOT/scripts/fs/FS.1097-build-history-chart-candidate.sh"
fi
docker image inspect "$IMAGE" >/dev/null

echo "FS1107_CREATE_BEGIN initial_network=$INITIAL_NETWORK image=$IMAGE"
CANDIDATE_ID="$(docker run -d --name "$NAME" --restart no \
  --network "$INITIAL_NETWORK" \
  --publish "127.0.0.1:${PORT}:777/tcp" \
  -e AIOPS_INTERNAL_TOKEN=fs1107-ephemeral-candidate-only \
  -e EXPLORER_ENABLED=1 \
  -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 \
  "$IMAGE")"
[[ -n "$CANDIDATE_ID" ]] || { echo "FS1107_ERROR=EMPTY_CANDIDATE_ID"; exit 2; }

check_stage() {
  local stage="$1"
  local runtime docker_port host_code
  runtime="$(docker inspect "$NAME" --format '{{json .NetworkSettings.Ports}}')"
  docker_port="$(docker port "$NAME" 777/tcp 2>&1 || true)"
  host_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/health" 2>/dev/null || true)"
  echo "FS1107_STAGE=$stage RUNTIME=$runtime DOCKER_PORT=$docker_port HOST_HTTP=$host_code"
  [[ "$runtime" == *"$PORT"* ]] || {
    echo "FS1107_ERROR=RUNTIME_BINDING_LOST stage=$stage"
    return 1
  }
  [[ "$host_code" == "200" ]] || {
    echo "FS1107_ERROR=HOST_HTTP_NOT_200 stage=$stage"
    return 1
  }
}

READY=NO
for attempt in $(seq 1 40); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/health" -o /dev/null; then
    READY=YES
    break
  fi
  sleep 1
done
echo "FS1107_HTTP_READY=$READY"
if [[ "$READY" != YES ]]; then
  docker logs --tail 40 "$NAME" 2>&1 || true
  exit 1
fi

check_stage INITIAL_EXTERNAL_NETWORK

for network in "${NETWORKS[@]}"; do
  echo "FS1107_CONNECT_BEGIN network=$network"
  docker network connect "$network" "$NAME"
  check_stage "AFTER_$network"
done

python3 - <<'PY'
import json, urllib.request
base="http://127.0.0.1:17898"
def get(path):
    with urllib.request.urlopen(base+path,timeout=10) as response:
        return response.status,dict(response.headers),response.read()
status,headers,body=get("/explorer/visual")
assert status==200,("visual_status",status)
# HTTP header field names are case-insensitive; normalize before validation.
headers={str(k).lower():str(v) for k,v in headers.items()}
csp=headers.get("content-security-policy","")
print("FS1107_CSP_HEADER="+csp,flush=True)
assert csp.count("sha256-")>=2 and "script-src" in csp and "style-src" in csp,("csp_missing_or_incomplete",csp)
assert "unsafe-inline" not in csp,("csp_unsafe_inline",csp)
for marker in (b'id="history-chart"',b'id="history-window"',b'id="history-metric"',b'id="history-refresh"'):
    assert marker in body,("history_markup_missing",marker.decode())
print("FS1107_VISUAL=200 CSP_HASHES=PASS HISTORY_MARKUP=PASS",flush=True)
for metric in ("availability","scrape_duration"):
    status,_,body=get("/api/fs1089/prometheus/history?metric="+metric+"&window=1h")
    assert status==200
    data=json.loads(body)
    assert data.get("metric")==metric and data.get("window")=="1h"
    assert len(data.get("series",[]))==5
    points=sum(len(item.get("points",[])) for item in data["series"])
    assert points>0
    print(f"FS1107_API metric={metric} STATUS=200 SERIES=5 POINTS={points}",flush=True)
PY

echo "FS1107_BROWSER_MATRIX_BEGIN"
"$PLAYWRIGHT_PY" "$ROOT/scripts/fs/fs1098_browser_history.py"
echo "FS1107_BROWSER_MATRIX_END"

echo "FS1107_FINAL_NETWORKS=$(docker inspect "$NAME" --format '{{json .NetworkSettings.Networks}}')"
echo "FS1107_CONTAINER_LOG_TAIL_BEGIN"
docker logs --tail 30 "$NAME" 2>&1 || true
echo "FS1107_CONTAINER_LOG_TAIL_END"

PROD_IMAGE_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1107_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE_BEFORE" ]] || {
  echo "FS1107_ERROR=PRODUCTION_IMAGE_CHANGED"
  exit 3
}
echo "FS1107_RESULT=PASS"
echo "FS1107_CANDIDATE_IMAGE=$IMAGE"
echo "FS1107_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1107_PRODUCTION_MUTATION=NONE"
