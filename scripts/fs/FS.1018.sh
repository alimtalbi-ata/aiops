#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1018 | CORE BATCHED PRE-CUTOVER GATE ====='
CORE=aiops2-rebuild-core
TWIN=aiops2-rebuild-twin
PROM=aiops2-rebuild-prometheus
OLD_ID=sha256:a41a250997460793b50b7eb5a5c41a637d1e39960ceb7e9664d2e1553bf784a7
NEW=aiops2-core:fs1017-metrics-candidate-20261106
F1=/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml
F2=/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml
WD=/home/aiops/aiops-prometheus-image-patch
test "${1:---plan}" = --plan || { echo 'NO_GO=ONLY_PLAN_SUPPORTED'; exit 2; }
test "$(docker inspect --format '{{.Image}}' "$CORE")" = "$OLD_ID" || { echo 'NO_GO=LIVE_CORE_IMAGE_CHANGED'; exit 1; }
test "$(docker inspect --format '{{.State.Running}}' "$CORE")" = true || { echo 'NO_GO=CORE_NOT_RUNNING'; exit 1; }
test "$(docker inspect --format '{{.State.Running}}' "$TWIN")" = true || { echo 'NO_GO=TWIN_NOT_RUNNING'; exit 1; }
docker image inspect "$OLD_ID" "$NEW" >/dev/null
test -f "$F1" && test -f "$F2"
echo '===== CONFIGURATION / ROLLBACK PRECHECK ====='
docker inspect "$CORE" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0];c=d["Config"];h=d["HostConfig"];nets=d["NetworkSettings"]["Networks"];l=c.get("Labels") or {}
assert l.get("com.docker.compose.project")=="aiops2-metrics-cutover"
assert l.get("com.docker.compose.service")=="aiops2-core"
assert l.get("com.docker.compose.project.config_files")=="/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml,/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml"
assert l.get("com.docker.compose.project.working_dir")=="/home/aiops/aiops-prometheus-image-patch"
assert c.get("Cmd")==["uvicorn","core.main:app","--host","0.0.0.0","--port","810"]
assert set(nets)=={"aiops2-rebuild-control","aiops2-rebuild-data"}
assert (h.get("RestartPolicy") or {}).get("Name")=="unless-stopped"
print("CORE_RUNTIME=PASS")
print("ROLLBACK_IMAGE_ID="+d["Image"])
print("COMPOSE_PROJECT="+l["com.docker.compose.project"])
print("COMPOSE_SERVICE="+l["com.docker.compose.service"])
print("NETWORKS="+",".join(sorted(nets)))
print("ENV_KEYS="+",".join(sorted(x.split("=",1)[0] for x in c.get("Env") or [])))
'
echo '===== CANDIDATE SOURCE AND ASGI CONTRACT ====='
docker run --rm -i --network none -e AIOPS_INTERNAL_TOKEN=fs1018-test-only --entrypoint python "$NEW" -B - <<'PY'
import asyncio
from contextlib import contextmanager
import core.main as m
from fastapi.responses import PlainTextResponse
@contextmanager
def db():
 class C:
  def execute(self,q):
   assert "from aiops.runs" in q.lower()
   return self
  def fetchone(self):return (12,3,2,7)
 yield C()
m.db=db
r=[r for r in m.app.routes if getattr(r,"path",None)=="/metrics"]
assert len(r)==1 and r[0].response_class is PlainTextResponse
async def test():
 messages=[]
 async def recv():return {"type":"http.request","body":b"","more_body":False}
 async def send(x):messages.append(x)
 await m.app({"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/metrics","raw_path":b"/metrics","query_string":b"","root_path":"","headers":[],"client":("127.0.0.1",1),"server":("127.0.0.1",810)},recv,send)
 s=next(x for x in messages if x["type"]=="http.response.start")
 h=dict(s["headers"]);b=b"".join(x.get("body",b"") for x in messages if x["type"]=="http.response.body")
 assert s["status"]==200
 assert h[b"content-type"].startswith(b"text/plain")
 assert b"aiops_runs_total 12\n" in b and b"aiops_runs_resolved 7\n" in b
 print("CORE_CANDIDATE_ASGI_HTTP=200")
 print("CORE_CANDIDATE_CONTENT_TYPE="+h[b"content-type"].decode())
 print("CORE_CANDIDATE_METRICS=PASS")
asyncio.run(test())
PY
echo '===== COMPOSE RENDER VALIDATION (NO SECRETS PRINTED) ====='
if docker compose version >/dev/null 2>&1; then
 (cd "$WD" && docker compose -p aiops2-metrics-cutover -f "$F1" -f "$F2" config --quiet)
 echo 'COMPOSE_CONFIG=PASS'
else
 echo 'COMPOSE_CONFIG=UNAVAILABLE'
fi
echo '===== PROMETHEUS STATUS ====='
docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
for t in d.get("data",{}).get("activeTargets",[]):
 j=t.get("labels",{}).get("job")
 if j in ("aiops2-core","aiops2-twin"):
  print("TARGET="+j+" HEALTH="+str(t.get("health"))+" ERROR="+str(t.get("lastError","")))
'
echo '===== CUTOVER SPECIFICATION (NOT EXECUTED) ====='
echo 'STRATEGY=COMPOSE_SCOPED_CORE_SERVICE_ONLY'
echo 'REQUIRED=override candidate image without editing existing compose files'
echo 'REQUIRED=preserve project service networks env volumes and existing config'
echo 'REQUIRED=preserve rollback image and original compose configuration'
echo 'REQUIRED=postcutover HTTP metrics content-type and Prometheus core UP'
echo 'REQUIRED=rollback Core only on failure; never modify Twin'
echo 'PRODUCTION_CORE_UNCHANGED=YES'
echo 'PRODUCTION_RESTARTED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'FS1018_RESULT=PLAN_PASS_DEPLOYMENT_APPROVAL_REQUIRED'
echo '===== END FS.1018 ====='
