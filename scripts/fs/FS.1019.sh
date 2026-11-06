#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1019 | CORE PRODUCTION COMPOSE CUTOVER / ROLLBACK ====='
MODE="${1:---plan}"
[[ "$MODE" == "--plan" || "$MODE" == "--execute" ]] || { echo 'USAGE: FS.1019.sh --plan|--execute'; exit 2; }
CORE=aiops2-rebuild-core
TWIN=aiops2-rebuild-twin
PROM=aiops2-rebuild-prometheus
PROJECT=aiops2-metrics-cutover
SERVICE=aiops2-core
OLD_ID=sha256:a41a250997460793b50b7eb5a5c41a637d1e39960ceb7e9664d2e1553bf784a7
NEW=aiops2-core:fs1017-metrics-candidate-20261106
F1=/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml
F2=/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml
WD=/home/aiops/aiops-prometheus-image-patch
[[ -f "$F1" && -f "$F2" && -d "$WD" ]] || { echo 'NO_GO=COMPOSE_FILES_MISSING'; exit 1; }
docker compose version >/dev/null
docker image inspect "$OLD_ID" "$NEW" >/dev/null
[[ "$(docker inspect --format '{{.Image}}' "$CORE")" == "$OLD_ID" ]] || { echo 'NO_GO=LIVE_CORE_IMAGE_CHANGED'; exit 1; }
[[ "$(docker inspect --format '{{.State.Running}}' "$CORE")" == true ]] || { echo 'NO_GO=CORE_NOT_RUNNING'; exit 1; }
[[ "$(docker inspect --format '{{.State.Running}}' "$TWIN")" == true ]] || { echo 'NO_GO=TWIN_NOT_RUNNING'; exit 1; }
docker inspect "$CORE" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0];c=d["Config"];l=c.get("Labels") or {};n=d["NetworkSettings"]["Networks"]
assert l.get("com.docker.compose.project")=="aiops2-metrics-cutover"
assert l.get("com.docker.compose.service")=="aiops2-core"
assert l.get("com.docker.compose.project.config_files")=="/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml,/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml"
assert set(n)=={"aiops2-rebuild-control","aiops2-rebuild-data"}
print("CORE_COMPOSE_GUARDS=PASS")
'
TMP="$(mktemp -d /tmp/fs1019.XXXXXXXX)"
chmod 700 "$TMP"
OVERRIDE="$TMP/candidate.yml"
ROLLBACK="$TMP/rollback.yml"
printf 'services:\n  aiops2-core:\n    image: %s\n' "$NEW" > "$OVERRIDE"
printf 'services:\n  aiops2-core:\n    image: %s\n' "$OLD_ID" > "$ROLLBACK"
chmod 600 "$OVERRIDE" "$ROLLBACK"
compose() { (cd "$WD" && docker compose -p "$PROJECT" -f "$F1" -f "$F2" "$@"); }
compose config --quiet
compose -f "$OVERRIDE" config --quiet
compose -f "$ROLLBACK" config --quiet
compose -f "$OVERRIDE" config --format json | python3 -c '
import json,sys
d=json.load(sys.stdin);s=d["services"]["aiops2-core"]
assert s["image"]=="aiops2-core:fs1017-metrics-candidate-20261106"
assert s.get("container_name") in ("aiops2-rebuild-core",None)
print("CANDIDATE_COMPOSE_RENDER=PASS")
'
echo '===== ISOLATED CANDIDATE ASGI CONTRACT ====='
docker run --rm -i --network none -e AIOPS_INTERNAL_TOKEN=fs1019-isolated-test-only --entrypoint python "$NEW" -B - <<'PY'
import asyncio
from contextlib import contextmanager
import core.main as m
@contextmanager
def fake_db():
 class C:
  def execute(self,q):
   assert "from aiops.runs" in q.lower()
   return self
  def fetchone(self):return (12,3,2,7)
 yield C()
m.db=fake_db
async def check():
 sent=[]
 async def recv():return {"type":"http.request","body":b"","more_body":False}
 async def send(x):sent.append(x)
 await m.app({"type":"http","asgi":{"version":"3.0"},"http_version":"1.1","method":"GET","scheme":"http","path":"/metrics","raw_path":b"/metrics","query_string":b"","root_path":"","headers":[],"client":("127.0.0.1",1),"server":("127.0.0.1",810)},recv,send)
 s=next(x for x in sent if x["type"]=="http.response.start")
 h=dict(s["headers"])
 body=b"".join(x.get("body",b"") for x in sent if x["type"]=="http.response.body")
 assert s["status"]==200 and h[b"content-type"].startswith(b"text/plain")
 assert b"aiops_runs_total 12\n" in body
 print("CANDIDATE_HTTP_METRICS=PASS")
asyncio.run(check())
PY
if [[ "$MODE" == "--plan" ]]; then
 rm -rf "$TMP"
 echo 'FS1019_RESULT=PLAN_PASS'
 echo 'PRODUCTION_RESTARTED=NO'
 exit 0
fi
[[ "${FS1019_APPROVE_CORE_PROD:-}" == "YES" ]] || { rm -rf "$TMP"; echo 'NO_GO=EXPLICIT_PROD_APPROVAL_REQUIRED'; exit 2; }
CHANGED=0
SUCCESS=0
cleanup() {
 local rc=$?
 trap - EXIT ERR INT TERM
 if [[ "$CHANGED" == 1 && "$SUCCESS" != 1 ]]; then
  echo '===== AUTOMATIC CORE ROLLBACK ====='
  if compose -f "$ROLLBACK" up -d --no-deps --force-recreate "$SERVICE"; then
   echo 'ROLLBACK_COMPOSE=RESTORED_OLD_IMAGE'
   docker inspect --format 'ROLLBACK_CORE_IMAGE={{.Image}} RUNNING={{.State.Running}}' "$CORE" || true
  else
   echo 'ROLLBACK_COMPOSE=FAILED_MANUAL_INTERVENTION_REQUIRED'
  fi
 fi
 rm -rf "$TMP"
 exit "$rc"
}
trap cleanup EXIT ERR INT TERM
echo '===== CORE ONLY COMPOSE RECREATE ====='
CHANGED=1
compose -f "$OVERRIDE" up -d --no-deps --force-recreate "$SERVICE"
[[ "$(docker inspect --format '{{.Image}}' "$CORE")" == "$(docker image inspect --format '{{.Id}}' "$NEW")" ]] || { echo 'NO_GO=CANDIDATE_IMAGE_NOT_RUNNING'; exit 1; }
echo '===== LIVE CORE HTTP METRICS ====='
for i in $(seq 1 30); do
 if docker exec -i "$CORE" python -B - <<'PY' >/dev/null 2>&1
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:810/metrics",timeout=4) as r:
 assert r.status==200
 assert r.headers.get("Content-Type","").startswith("text/plain")
 body=r.read()
 assert b"aiops_runs_total " in body
PY
 then echo 'LIVE_CORE_HTTP_METRICS=PASS'; break; fi
 if [[ "$i" == 30 ]]; then echo 'LIVE_CORE_HTTP_METRICS=FAIL'; exit 1; fi
 sleep 2
done
echo '===== PROMETHEUS CORE + TWIN TARGETS ====='
for i in $(seq 1 30); do
 if docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
for job in ("aiops2-core","aiops2-twin"):
 a=[x for x in d.get("data",{}).get("activeTargets",[]) if x.get("labels",{}).get("job")==job]
 assert len(a)==1 and a[0].get("health")=="up",job
' 2>/dev/null; then echo 'PROMETHEUS_CORE=UP'; echo 'PROMETHEUS_TWIN=UP'; break; fi
 if [[ "$i" == 30 ]]; then echo 'PROMETHEUS_CORE_OR_TWIN=NOT_UP'; exit 1; fi
 sleep 3
done
SUCCESS=1
echo 'PRODUCTION_CORE_CUTOVER=PASS'
echo 'FS1019_RESULT=PASS'
echo 'ROLLBACK_IMAGE_RETAINED=YES'
echo 'COMPOSE_FILES_UNCHANGED=YES'
