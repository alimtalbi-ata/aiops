#!/usr/bin/env bash
set -euo pipefail
NAME=aiops2-fs1090-history-temp
IMAGE=aiops2-portal:fs1089-history-candidate
PORT=17890
echo "FS1090_MODE=TEMPORARY_CANDIDATE_API_TEST"
docker image inspect "$IMAGE" >/dev/null
if docker container inspect "$NAME" >/dev/null 2>&1; then
 echo "FS1090_ERROR=TEMP_CONTAINER_ALREADY_EXISTS";exit 2
fi
if [[ "$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')" != "aiops2-portal:fs1073-csp-candidate" ]];then
 echo "FS1090_ERROR=UNEXPECTED_PRODUCTION_IMAGE";exit 2
fi
cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run -d --name "$NAME" --restart=no --network aiops2-rebuild-integration -p "127.0.0.1:$PORT:777" \
 -e AIOPS_INTERNAL_TOKEN=fs1090-local-test-token \
 -e EXPLORER_ENABLED=1 \
 -e EXPLORER_ALLOWED_CIDRS=0.0.0.0/0 \
 "$IMAGE" >/dev/null
docker network connect aiops2-rebuild-control "$NAME"
docker network connect aiops2-rebuild-public "$NAME"
for attempt in $(seq 1 35);do
 if curl -fsS --max-time 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1;then
  echo "FS1090_HTTP_READY=YES ATTEMPT=$attempt";break
 fi
 if [[ "$attempt" == 35 ]];then echo "FS1090_HTTP_READY=NO";exit 1;fi
 sleep 1
done
python3 - "$PORT" <<'PY'
import json,sys,urllib.error,urllib.parse,urllib.request
port=int(sys.argv[1]);base=f"http://127.0.0.1:{port}"
def req(path,headers=None):
 request=urllib.request.Request(base+path,headers=headers or {})
 try:
  with urllib.request.urlopen(request,timeout=12) as r:
   return r.status,r.read(3000000),dict(r.headers)
 except urllib.error.HTTPError as e:
  return e.code,e.read(50000),dict(e.headers)
for metric in ("availability","scrape_duration"):
 for window in ("1h","6h","24h"):
  qs=urllib.parse.urlencode({"metric":metric,"window":window})
  status,body,_=req("/api/fs1089/prometheus/history?"+qs)
  assert status==200,(metric,window,status,body[:250])
  d=json.loads(body)
  assert d["metric"]==metric and d["window"]==window
  assert len(d["series"])>=1,(metric,window,"empty series")
  assert all(isinstance(s["points"],list) and len(s["points"])<=260 for s in d["series"])
  assert any(s["points"] for s in d["series"]),(metric,window,"empty history")
  print(f"FS1090_HISTORY metric={metric} window={window} STATUS=200 SERIES={len(d['series'])} POINTS={sum(len(s['points']) for s in d['series'])}",flush=True)
for qs in ("metric=process_cpu_seconds_total","window=1y","metric=up%7Bjob%3D%22foo%22%7D"):
 status,body,_=req("/api/fs1089/prometheus/history?"+qs)
 assert status==400,(qs,status,body[:200])
 print("FS1090_INVALID_QUERY=REJECTED_400",flush=True)
status,body,_=req("/explorer/visual")
assert status==200 and b'id="graph"' in body
print("FS1090_LEGACY_VISUAL=PASS",flush=True)
PY
echo "FS1090_PRODUCTION_DEPLOY=NOT_PERFORMED"
echo "FS1090_RESULT=PASS"
