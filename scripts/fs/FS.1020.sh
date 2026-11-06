#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1020 | POST-CUTOVER AUDIT + PERSISTENCE READINESS ====='
[[ "${1:---audit}" == --audit ]] || { echo 'NO_GO=AUDIT_ONLY'; exit 2; }
CORE=aiops2-rebuild-core
TWIN=aiops2-rebuild-twin
PROM=aiops2-rebuild-prometheus
PROJECT=aiops2-metrics-cutover
SERVICE=aiops2-core
CANDIDATE=aiops2-core:fs1017-metrics-candidate-20261106
OLD_ID=sha256:a41a250997460793b50b7eb5a5c41a637d1e39960ceb7e9664d2e1553bf784a7
F1=/home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml
F2=/home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml
WD=/home/aiops/aiops-prometheus-image-patch
test -f "$F1" && test -f "$F2"
docker compose version >/dev/null
docker image inspect "$OLD_ID" "$CANDIDATE" >/dev/null
echo '===== LIVE IMAGE / CONTAINER GUARDS ====='
docker inspect "$CORE" "$TWIN" | python3 -c '
import json,sys
a=json.load(sys.stdin);c,t=a
assert c["State"]["Running"] and t["State"]["Running"]
l=c["Config"].get("Labels") or {}
assert l.get("com.docker.compose.project")=="aiops2-metrics-cutover"
assert l.get("com.docker.compose.service")=="aiops2-core"
assert set(c["NetworkSettings"]["Networks"])=={"aiops2-rebuild-control","aiops2-rebuild-data"}
print("CORE_RUNNING=YES")
print("TWIN_RUNNING=YES")
print("CORE_LIVE_IMAGE_ID="+c["Image"])
print("TWIN_LIVE_IMAGE_ID="+t["Image"])
print("CORE_NETWORKS="+",".join(sorted(c["NetworkSettings"]["Networks"])))
'
ACTUAL="$(docker inspect --format '{{.Image}}' "$CORE")"
EXPECTED="$(docker image inspect --format '{{.Id}}' "$CANDIDATE")"
[[ "$ACTUAL" == "$EXPECTED" ]] || { echo 'NO_GO=CORE_NOT_ON_APPROVED_CANDIDATE'; exit 1; }
echo 'CORE_CANDIDATE_IMAGE=PASS'
echo '===== LIVE METRICS ====='
docker exec -i "$CORE" python -B - <<'PY'
import urllib.request
with urllib.request.urlopen("http://127.0.0.1:810/metrics",timeout=8) as r:
 assert r.status==200
 ct=r.headers.get("Content-Type","")
 assert ct.startswith("text/plain"),ct
 b=r.read()
 for metric in (b"aiops_runs_total ",b"aiops_runs_running ",b"aiops_runs_blocked ",b"aiops_runs_resolved "):
  assert metric in b,metric
 print("CORE_LIVE_METRICS=PASS")
 print("CORE_LIVE_CONTENT_TYPE="+ct)
PY
echo '===== PROMETHEUS LIVE TARGETS ====='
docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
for job in ("aiops2-core","aiops2-twin"):
 a=[x for x in d.get("data",{}).get("activeTargets",[]) if x.get("labels",{}).get("job")==job]
 assert len(a)==1,(job,len(a))
 t=a[0];print("PROMETHEUS_"+job.upper().replace("-","_")+"="+str(t.get("health")).upper())
 assert t.get("health")=="up",(job,t.get("lastError"))
'
echo '===== PERSISTENT COMPOSE CONFIG / DRIFT ====='
(cd "$WD" && docker compose -p "$PROJECT" -f "$F1" -f "$F2" config --quiet)
(cd "$WD" && docker compose -p "$PROJECT" -f "$F1" -f "$F2" config --format json) | python3 -c '
import json,sys
d=json.load(sys.stdin);s=d["services"]["aiops2-core"]
print("PERSISTENT_CORE_IMAGE="+str(s.get("image","<build-only>")))
print("PERSISTENT_CORE_CONTAINER_NAME="+str(s.get("container_name","<auto>")))
print("PERSISTENT_CORE_NETWORKS="+",".join(sorted(s.get("networks") or {})))
print("PERSISTENT_CORE_HAS_BUILD="+str(bool(s.get("build"))).upper())
'
PERSISTENT_IMAGE="$(cd "$WD" && docker compose -p "$PROJECT" -f "$F1" -f "$F2" config --format json | python3 -c 'import json,sys;print(json.load(sys.stdin)["services"]["aiops2-core"].get("image",""))')"
if [[ "$PERSISTENT_IMAGE" == "$CANDIDATE" ]]; then
 echo 'PERSISTENCE_STATUS=ALIGNED'
else
 echo 'PERSISTENCE_STATUS=DRIFT'
 echo 'PERSISTENCE_ACTION=REQUIRES_SEPARATE_EXPLICIT_APPROVAL'
fi
echo '===== ORIGINAL CONFIG FINGERPRINTS ====='
sha256sum "$F1" "$F2"
echo '===== RECOVERY INVENTORY ====='
docker image inspect "$OLD_ID" --format 'ROLLBACK_CORE_IMAGE_PRESENT=YES IMAGE_ID={{.Id}}'
docker ps --filter name=aiops2-rebuild-twin --format 'TWIN_CONTAINER={{.Names}} STATE={{.Status}}'
echo '===== READ-ONLY GUARANTEES ====='
echo 'PRODUCTION_RESTARTED=NO'
echo 'COMPOSE_FILES_MODIFIED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'FS1020_RESULT=AUDIT_PASS'
echo '===== END FS.1020 ====='
