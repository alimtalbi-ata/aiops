#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1014 | TWIN CUTOVER PLAN + ROLLBACK ====='
NAME=aiops2-rebuild-twin
CANDIDATE=aiops2-twin:fs1009-decimal-metrics-candidate-20261106
EXPECTED_CANDIDATE_SHA=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb
EXPECTED_BASE_ID=sha256:73fde0a153e9c41d20b3e3fdfb0fc9d3442399aa6cd2dccf34b2b09d88cbb9c6
MODE="${1:-plan}"
if [ "$MODE" != plan ]; then
  echo 'REFUSED: FS.1014 is a non-mutating plan only; no deployment flag is supported.'
  exit 2
fi
docker inspect "$NAME" >/dev/null
docker image inspect "$CANDIDATE" >/dev/null
BASE_ID="$(docker inspect --format '{{.Image}}' "$NAME")"
if [ "$BASE_ID" != "$EXPECTED_BASE_ID" ]; then
  echo 'NO_GO=LIVE_TWIN_IMAGE_CHANGED'
  exit 1
fi
RUNNING="$(docker inspect --format '{{.State.Running}}' "$NAME")"
test "$RUNNING" = true || { echo 'NO_GO=TWIN_NOT_RUNNING'; exit 1; }
CANDIDATE_SHA="$(docker run --rm --network none --entrypoint sha256sum "$CANDIDATE" /app/twin/fs_observations.py | awk '{print $1}')"
test "$CANDIDATE_SHA" = "$EXPECTED_CANDIDATE_SHA" || { echo 'NO_GO=CANDIDATE_SOURCE_MISMATCH'; exit 1; }
echo 'CANDIDATE_SOURCE_SHA=PASS'
echo 'BASE_IMAGE_ID_MATCH=PASS'
docker inspect "$NAME" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]; cfg=d.get("Config") or {}; h=d.get("HostConfig") or {}
net=(d.get("NetworkSettings") or {}).get("Networks") or {}
assert cfg.get("Cmd")==["uvicorn","twin.main:app","--host","0.0.0.0","--port","811"],"unexpected CMD"
assert h.get("NetworkMode")=="aiops2-rebuild-control","unexpected primary network"
assert set(net)=={"aiops2-rebuild-control","aiops2-rebuild-data"},"unexpected networks"
assert all("aiops2-twin" in (n.get("Aliases") or []) for n in net.values()),"missing DNS alias"
assert (h.get("RestartPolicy") or {}).get("Name")=="unless-stopped","unexpected restart policy"
assert not d.get("Mounts"),"unexpected mounts"
assert not (h.get("PortBindings") or {}),"unexpected published ports"
assert not (cfg.get("Labels") or {}).get("com.docker.compose.project"),"Compose-managed Twin"
print("RUNTIME_SHAPE=PASS")
print("ENV_KEY_COUNT="+str(len(cfg.get("Env") or [])))
print("NETWORKS="+",".join(sorted(net)))
print("ROLLBACK_IMAGE_ID="+str(d.get("Image")))
print("ROLLBACK_IMAGE_REF="+str(cfg.get("Image")))
print("ROLLBACK_IMAGE_PRESENT=CHECK_SEPARATELY")
'
docker image inspect "$EXPECTED_BASE_ID" >/dev/null
echo 'ROLLBACK_IMAGE_PRESENT=YES'
echo '===== CONTROLLED CUTOVER SEQUENCE (NOT EXECUTED) ====='
echo 'STEP_1=explicit separate production approval and maintenance window'
echo 'STEP_2=save complete Docker inspect in a rootless 0600 private location (contains secrets)'
echo 'STEP_3=save current container by rename; never delete before candidate health succeeds'
echo 'STEP_4=create candidate with preserved env, command, healthcheck, networks and aliases'
echo 'STEP_5=verify application health, /metrics HTTP 200, Prometheus target UP and FS value'
echo 'STEP_6=on any failure remove candidate and restore original container name and start'
echo 'STEP_7=retain old image and rollback instructions until acceptance'
echo 'CUTOVER_SCRIPT=NOT_AUTHORIZED'
echo 'PRODUCTION_RESTARTED=NO'
echo 'PRODUCTION_DEPLOYED=NO'
echo 'DATABASE_WRITES=0'
echo 'HTTP_WRITES=0'
echo 'FS1014_RESULT=PLAN_PASS_APPROVAL_REQUIRED'
echo '===== END FS.1014 ====='
