#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1012 | READ-ONLY DEPLOYMENT QUALIFICATION ====='
echo 'MODE=READ_ONLY'
echo 'PRODUCTION_CHANGES=NONE'
TWIN=aiops2-rebuild-twin
CORE=aiops2-rebuild-core
PROM=aiops2-rebuild-prometheus
CANDIDATE=aiops2-twin:fs1009-decimal-metrics-candidate-20261106
EXPECTED_SOURCE_SHA=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb

echo '===== RUNTIME CONTAINER INVENTORY (NO ENV OR SECRET VALUES) ====='
for c in "$TWIN" "$CORE" "$PROM"; do
  echo "CONTAINER=$c"
  if ! docker inspect "$c" >/dev/null 2>&1; then
    echo 'CONTAINER_FOUND=NO'
    continue
  fi
  docker inspect "$c" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]
cfg=d.get("Config") or {}
host=d.get("HostConfig") or {}
state=d.get("State") or {}
labels=cfg.get("Labels") or {}
print("CONTAINER_FOUND=YES")
print("RUNNING="+str(state.get("Running")))
print("IMAGE_TAG="+str(cfg.get("Image")))
print("IMAGE_ID="+str(d.get("Image")))
print("RESTART_POLICY="+str((host.get("RestartPolicy") or {}).get("Name")))
print("NETWORK_MODE="+str(host.get("NetworkMode")))
print("NETWORK_NAMES="+",".join(sorted((d.get("NetworkSettings") or {}).get("Networks",{}).keys())))
for key in ("com.docker.compose.project","com.docker.compose.service","com.docker.compose.project.config_files","com.docker.compose.project.working_dir"):
 print("LABEL_"+key+"="+str(labels.get(key,"UNSET")))
for m in d.get("Mounts",[]):
 print("MOUNT="+str(m.get("Type"))+" "+str(m.get("Destination"))+" RW="+str(m.get("RW")))
'
done

echo '===== CANDIDATE IMAGE ID AND PATCH SHA ====='
if docker image inspect "$CANDIDATE" >/dev/null 2>&1; then
  docker image inspect "$CANDIDATE" --format 'CANDIDATE_IMAGE_ID={{.Id}}'
  ACTUAL_SHA="$(docker run --rm --network none --entrypoint sha256sum "$CANDIDATE" /app/twin/fs_observations.py | awk '{print $1}')"
  if [ "$ACTUAL_SHA" = "$EXPECTED_SOURCE_SHA" ]; then
    echo 'CANDIDATE_SOURCE_SHA=PASS'
  else
    echo "CANDIDATE_SOURCE_SHA=MISMATCH:$ACTUAL_SHA"
  fi
else
  echo 'CANDIDATE_IMAGE_FOUND=NO'
fi

echo '===== PROMETHEUS TARGET HEALTH SNAPSHOT (GET ONLY) ====='
if docker inspect "$PROM" >/dev/null 2>&1; then
  if docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
assert d.get("status")=="success", "prometheus API did not return success"
for t in d.get("data",{}).get("activeTargets",[]):
 job=t.get("labels",{}).get("job","")
 if job in ("aiops2-core","aiops2-twin"):
  print("JOB="+job)
  print("SCRAPE_URL="+str(t.get("scrapeUrl","")))
  print("HEALTH="+str(t.get("health","")))
  print("LAST_ERROR="+str(t.get("lastError","")))
  print("LAST_SCRAPE="+str(t.get("lastScrape","")))
'; then
    echo 'PROMETHEUS_TARGET_QUERY=PASS'
  else
    echo 'PROMETHEUS_TARGET_QUERY=FAIL'
  fi
fi

echo '===== ROLLBACK INVENTORY ====='
echo 'ROLLBACK_ACTION=NOT_EXECUTED'
echo 'ROLLBACK_REQUIREMENTS=record current image IDs, compose config files, service names, candidate digest and approval'
echo 'PRODUCTION_RESTARTED=NO'
echo 'PRODUCTION_DEPLOYED=NO'
echo 'HTTP_WRITES=0'
echo 'DATABASE_WRITES=0'
echo 'FS1012_RESULT=INVENTORY_COMPLETE_REVIEW_REQUIRED'
echo '===== END FS.1012 ====='
