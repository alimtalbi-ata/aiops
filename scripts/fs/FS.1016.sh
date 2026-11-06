#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1016 | CORE READ-ONLY CUTOVER PREFLIGHT ====='
CORE=aiops2-rebuild-core
EXPECTED_ID=sha256:a41a250997460793b50b7eb5a5c41a637d1e39960ceb7e9664d2e1553bf784a7
PROM=aiops2-rebuild-prometheus
docker inspect "$CORE" >/dev/null
docker image inspect "$EXPECTED_ID" >/dev/null
test "$(docker inspect --format '{{.Image}}' "$CORE")" = "$EXPECTED_ID" || { echo 'NO_GO=CORE_IMAGE_CHANGED'; exit 1; }
test "$(docker inspect --format '{{.State.Running}}' "$CORE")" = true || { echo 'NO_GO=CORE_NOT_RUNNING'; exit 1; }
docker inspect "$CORE" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0];c=d.get("Config") or {};h=d.get("HostConfig") or {}
net=(d.get("NetworkSettings") or {}).get("Networks") or {}
assert c.get("Cmd")==["uvicorn","core.main:app","--host","0.0.0.0","--port","810"],"unexpected command"
assert set(net)=={"aiops2-rebuild-control","aiops2-rebuild-data"},"unexpected networks"
assert h.get("NetworkMode")=="aiops2-rebuild-control","unexpected network mode"
assert (h.get("RestartPolicy") or {}).get("Name")=="unless-stopped","unexpected restart policy"
labels=c.get("Labels") or {}
assert labels.get("com.docker.compose.project")=="aiops2-metrics-cutover","unexpected compose project"
assert labels.get("com.docker.compose.service")=="aiops2-core","unexpected compose service"
print("CORE_RUNTIME_GUARDS=PASS")
print("CORE_IMAGE_ID="+str(d.get("Image")))
print("CORE_IMAGE_REF="+str(c.get("Image")))
print("CORE_ENV_KEY_COUNT="+str(len(c.get("Env") or [])))
print("CORE_NETWORKS="+",".join(sorted(net)))
print("CORE_COMPOSE_PROJECT="+str(labels.get("com.docker.compose.project")))
print("CORE_COMPOSE_SERVICE="+str(labels.get("com.docker.compose.service")))
print("CORE_COMPOSE_FILES="+str(labels.get("com.docker.compose.project.config_files")))
print("CORE_COMPOSE_WORKDIR="+str(labels.get("com.docker.compose.project.working_dir")))
'
echo '===== LIVE CORE /METRICS RESPONSE (NO WRITES) ====='
docker exec -i "$CORE" python -B - <<'PY'
import urllib.request,urllib.error
url="http://127.0.0.1:810/metrics"
try:
 with urllib.request.urlopen(url,timeout=8) as r:
  print("CORE_METRICS_HTTP="+str(r.status))
  print("CORE_METRICS_CONTENT_TYPE="+str(r.headers.get("Content-Type")))
  body=r.read(500000)
  print("CORE_METRICS_BYTES="+str(len(body)))
except urllib.error.HTTPError as e:
 print("CORE_METRICS_HTTP="+str(e.code))
 print("CORE_METRICS_CONTENT_TYPE="+str(e.headers.get("Content-Type")))
except Exception as e:
 print("CORE_METRICS_CHECK_ERROR="+type(e).__name__)
PY
echo '===== LIVE CORE SOURCE /METRICS CONTRACT ====='
docker exec -i "$CORE" python -B - <<'PY'
import inspect
from core.main import app
for route in app.routes:
 if getattr(route,"path",None)=="/metrics":
  print("METRICS_ROUTE_METHODS="+",".join(sorted(getattr(route,"methods",[]) or [])))
  print("METRICS_ROUTE_RESPONSE_CLASS="+getattr(getattr(route,"response_class",None),"__name__","unknown"))
  print("METRICS_ROUTE_ENDPOINT="+getattr(route.endpoint,"__name__","unknown"))
PY
echo '===== COMPOSE FILE EXISTENCE (READ ONLY) ====='
for f in /home/aiops/aiops-prometheus-image-patch/compose.metrics-cutover.yml /home/aiops/aiops2-patches/fs-core-real-registration/compose.fs-core.override.yml; do
 if [[ -f "$f" ]]; then sha256sum "$f"; else echo "NO_GO=MISSING_COMPOSE_FILE:$f"; exit 1; fi
done
echo '===== PROMETHEUS TARGET STATUS (READ ONLY) ====='
docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
for t in d.get("data",{}).get("activeTargets",[]):
 job=t.get("labels",{}).get("job","")
 if job in ("aiops2-core","aiops2-twin"):
  print("TARGET="+job+" HEALTH="+str(t.get("health"))+" ERROR="+str(t.get("lastError","")))
'
echo '===== SAFETY ====='
echo 'CORE_CONTAINER_CREATED=NO'
echo 'CORE_CONTAINER_STOPPED=NO'
echo 'PRODUCTION_RESTARTED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'FS1016_RESULT=PREFLIGHT_COMPLETE_REVIEW_REQUIRED'
echo '===== END FS.1016 ====='
