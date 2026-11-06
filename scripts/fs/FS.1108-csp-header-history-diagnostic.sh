#!/usr/bin/env bash
set -euo pipefail

IMAGE=aiops2-portal:fs1097-history-chart-candidate
PROD=aiops2-rebuild-portal
NAME=aiops2-fs1108-csp-header-diagnostic
PORT=17898
INITIAL_NETWORK=aiops2-rebuild-public
NETWORKS=(aiops2-rebuild-control aiops2-rebuild-integration aiops2-rebuild-observability)

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "FS1108_MODE=READ_ONLY_CANDIDATE_CSP_AND_HISTORY_HTTP_DIAGNOSTIC"
PROD_IMAGE_BEFORE="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1108_PRODUCTION_IMAGE_BEFORE=$PROD_IMAGE_BEFORE"
[[ "$PROD_IMAGE_BEFORE" == "aiops2-portal:fs1073-csp-candidate" ]]
docker image inspect "$IMAGE" >/dev/null
for network in "$INITIAL_NETWORK" "${NETWORKS[@]}"; do docker network inspect "$network" >/dev/null; done
if docker container inspect "$NAME" >/dev/null 2>&1; then
  echo "FS1108_ERROR=TEMP_NAME_ALREADY_EXISTS"; exit 2
fi
if ss -ltnH "sport = :$PORT" 2>/dev/null | grep -q .; then
  echo "FS1108_ERROR=HOST_PORT_ALREADY_LISTENING"; exit 2
fi

docker run -d --name "$NAME" --restart no --network "$INITIAL_NETWORK" \
  -p "127.0.0.1:$PORT:777/tcp" \
  -e AIOPS_INTERNAL_TOKEN=fs1108-ephemeral-diagnostic-only \
  -e EXPLORER_ENABLED=1 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 "$IMAGE" >/dev/null

ready=NO
for attempt in $(seq 1 40); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "http://127.0.0.1:$PORT/health" 2>/dev/null || true)"
  if [[ "$code" == 200 ]]; then ready=YES; break; fi
  sleep 1
done
echo "FS1108_HEALTH_READY=$ready"
[[ "$ready" == YES ]]
for network in "${NETWORKS[@]}"; do
  docker network connect "$network" "$NAME"
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/health" 2>/dev/null || true)"
  echo "FS1108_NETWORK_STAGE=$network HOST_HTTP=$code"
  [[ "$code" == 200 ]]
done

python3 - <<'PY'
import json, urllib.error, urllib.request
base="http://127.0.0.1:17898"
def fetch(path):
    req=urllib.request.Request(base+path,headers={"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=10) as r:
            return r.status,list(r.headers.items()),r.read()
    except urllib.error.HTTPError as e:
        return e.code,list(e.headers.items()),e.read()
status,headers,body=fetch("/explorer/visual")
print("FS1108_VISUAL_STATUS="+str(status))
print("FS1108_VISUAL_HEADER_NAMES="+",".join(k for k,v in headers))
for key,value in headers:
    if key.lower()=="content-security-policy":
        print("FS1108_CSP_VALUE="+value)
print("FS1108_VISUAL_BODY_BYTES="+str(len(body)))
for marker in (b'history-chart',b'history-window',b'history-metric',b'history-refresh'):
    print("FS1108_MARKER_"+marker.decode().upper().replace("-","_")+"="+("YES" if marker in body else "NO"))
for metric in ("availability","scrape_duration"):
    status,headers,body=fetch("/api/fs1089/prometheus/history?metric="+metric+"&window=1h")
    print("FS1108_HISTORY metric="+metric+" STATUS="+str(status)+" BODY_BYTES="+str(len(body)))
    if status==200:
        try:
            data=json.loads(body)
            print("FS1108_HISTORY_SCHEMA metric="+metric+" keys="+",".join(sorted(data.keys()))+
                  " metric_match="+str(data.get("metric")==metric)+
                  " window_match="+str(data.get("window")=="1h")+
                  " series="+str(len(data.get("series",[])))+
                  " points="+str(sum(len(s.get("points",[])) for s in data.get("series",[]))))
        except Exception as exc:
            print("FS1108_HISTORY_JSON_ERROR metric="+metric+" "+type(exc).__name__)
    else:
        print("FS1108_HISTORY_ERROR_BODY="+body[:400].decode("utf-8","replace").replace("\n"," "))
PY

echo "FS1108_LOG_TAIL_BEGIN"
docker logs --tail 30 "$NAME" 2>&1 || true
echo "FS1108_LOG_TAIL_END"
PROD_IMAGE_AFTER="$(docker inspect "$PROD" --format '{{.Config.Image}}')"
echo "FS1108_PRODUCTION_IMAGE_AFTER=$PROD_IMAGE_AFTER"
[[ "$PROD_IMAGE_AFTER" == "$PROD_IMAGE_BEFORE" ]]
echo "FS1108_RESULT=DIAGNOSTIC_COMPLETE"
echo "FS1108_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1108_PRODUCTION_MUTATION=NONE"
