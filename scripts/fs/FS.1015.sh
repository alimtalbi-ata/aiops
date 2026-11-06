#!/usr/bin/env bash
set -Eeuo pipefail
echo '===== FS.1015 | TWIN PRODUCTION CUTOVER WITH AUTOMATIC ROLLBACK ====='
NAME=aiops2-rebuild-twin
OLD_IMAGE_ID=sha256:73fde0a153e9c41d20b3e3fdfb0fc9d3442399aa6cd2dccf34b2b09d88cbb9c6
NEW_IMAGE=aiops2-twin:fs1009-decimal-metrics-candidate-20261106
EXPECTED_SHA=2cedd1ae5802c82f8d09f7fd7dd78280b3591c48929de4cc16a504487fe59edb
PROM=aiops2-rebuild-prometheus
MODE="${1:---plan}"
if [[ "$MODE" != "--plan" && "$MODE" != "--execute" ]]; then echo 'USAGE: FS.1015.sh --plan|--execute'; exit 2; fi
docker inspect "$NAME" >/dev/null
docker image inspect "$NEW_IMAGE" >/dev/null
test "$(docker inspect --format '{{.Image}}' "$NAME")" = "$OLD_IMAGE_ID" || { echo 'NO_GO=BASE_IMAGE_CHANGED'; exit 1; }
test "$(docker inspect --format '{{.State.Running}}' "$NAME")" = true || { echo 'NO_GO=BASE_NOT_RUNNING'; exit 1; }
test "$(docker run --rm --network none --entrypoint sha256sum "$NEW_IMAGE" /app/twin/fs_observations.py | awk '{print $1}')" = "$EXPECTED_SHA" || { echo 'NO_GO=SOURCE_SHA_MISMATCH'; exit 1; }
docker image inspect "$OLD_IMAGE_ID" >/dev/null
docker inspect "$NAME" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0];c=d["Config"];h=d["HostConfig"];net=d["NetworkSettings"]["Networks"]
assert c["Cmd"]==["uvicorn","twin.main:app","--host","0.0.0.0","--port","811"]
assert not c.get("Entrypoint")
assert h["NetworkMode"]=="aiops2-rebuild-control"
assert set(net)=={"aiops2-rebuild-control","aiops2-rebuild-data"}
assert all("aiops2-twin" in (x.get("Aliases") or []) for x in net.values())
assert (h.get("RestartPolicy") or {}).get("Name")=="unless-stopped"
assert not d.get("Mounts") and not (h.get("PortBindings") or {})
assert not h.get("Privileged") and not h.get("ReadonlyRootfs")
assert not h.get("CapAdd") and not h.get("CapDrop")
assert not h.get("SecurityOpt") and not h.get("PidMode")
assert not (c.get("Labels") or {}).get("com.docker.compose.project")
assert not (h.get("Devices") or []) and not (h.get("Binds") or [])
assert not (h.get("ExtraHosts") or []) and not (h.get("Dns") or [])
assert not (h.get("VolumesFrom") or []) and not (h.get("Links") or [])
assert not (h.get("Tmpfs") or {})
assert not (h.get("Memory") or 0) and not (h.get("NanoCpus") or 0)
assert not (h.get("CpuQuota") or 0) and not (h.get("CpusetCpus") or "")
assert c.get("User") in ("",None)
assert c.get("WorkingDir")=="/app"
assert c.get("Healthcheck") is not None
print("RUNTIME_GUARDS=PASS")
'
echo 'CANDIDATE_SHA=PASS'
echo 'ROLLBACK_IMAGE_PRESENT=YES'
if [[ "$MODE" == "--plan" ]]; then
 echo 'FS1015_RESULT=PLAN_PASS'
 echo 'EXECUTION=NOT_STARTED'
 echo 'PRODUCTION_RESTARTED=NO'
 exit 0
fi
if [[ "${FS1015_APPROVE_TWIN_CUTOVER:-}" != "YES" ]]; then
 echo 'NO_GO=EXPLICIT_ENV_APPROVAL_REQUIRED'
 echo 'Set FS1015_APPROVE_TWIN_CUTOVER=YES only for an approved production maintenance window.'
 exit 2
fi
TMP="$(mktemp -d /tmp/fs1015.XXXXXXXX)"
chmod 700 "$TMP"
OLD_NAME="${NAME}-fs1015-rollback"
CHANGED=0
SUCCESS=0
rollback() {
 local code=$?
 trap - ERR EXIT INT TERM
 if [[ "$CHANGED" == 1 && "$SUCCESS" != 1 ]]; then
  echo '===== AUTOMATIC ROLLBACK ====='
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  if docker inspect "$OLD_NAME" >/dev/null 2>&1; then
   docker rename "$OLD_NAME" "$NAME" && docker start "$NAME"
   echo 'ROLLBACK=OLD_CONTAINER_RESTORED'
  else
   echo 'ROLLBACK=FAILED_OLD_CONTAINER_MISSING'
  fi
 fi
 rm -rf "$TMP"
 exit "$code"
}
trap rollback ERR EXIT INT TERM
test ! -e "$TMP/inspect.json"
docker inspect "$NAME" > "$TMP/inspect.json"
chmod 600 "$TMP/inspect.json"
python3 - "$TMP/inspect.json" "$TMP/container.env" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))[0]
env=d["Config"].get("Env") or []
with open(sys.argv[2],"w") as out:
 for item in env:
  assert "=" in item and "\n" not in item and "\r" not in item
  key,val=item.split("=",1)
  assert key and all(c not in key for c in " =\t")
  out.write(item+"\n")
PY
chmod 600 "$TMP/container.env"
docker inspect "$OLD_NAME" >/dev/null 2>&1 && { echo 'NO_GO=ROLLBACK_NAME_ALREADY_EXISTS'; exit 1; }
echo '===== STOP AND PRESERVE ORIGINAL CONTAINER ====='
CHANGED=1
docker stop --time 15 "$NAME" >/dev/null
docker rename "$NAME" "$OLD_NAME"
echo '===== CREATE CANDIDATE WITH ORIGINAL CONFIG ====='
docker run -d --name "$NAME" \
 --network aiops2-rebuild-control --network-alias aiops2-twin \
 --env-file "$TMP/container.env" \
 --restart unless-stopped \
 --workdir /app \
 "$NEW_IMAGE" >/dev/null
docker network connect --alias aiops2-twin aiops2-rebuild-data "$NAME"
echo '===== CANDIDATE HEALTH AND METRICS ====='
for i in $(seq 1 30); do
 state="$(docker inspect --format '{{.State.Status}}' "$NAME")"
 if [[ "$state" != running ]]; then echo "CANDIDATE_STATE=$state"; exit 1; fi
 if docker exec -i "$NAME" python -B - <<'PY' >/dev/null 2>&1
from twin.fs_observations import fs_lab_metrics
r=fs_lab_metrics()
assert b'aiops_twin_fs_lab_used_percent' in r.body
assert b'aiops_twin_fs_lab_alert_firing' in r.body
PY
 then echo 'CANDIDATE_FS_METRICS=PASS'; break; fi
 if [[ "$i" == 30 ]]; then echo 'CANDIDATE_FS_METRICS=FAIL'; exit 1; fi
 sleep 2
done
echo '===== PROMETHEUS TWIN TARGET ====='
for i in $(seq 1 30); do
 if docker exec "$PROM" wget -qO- http://127.0.0.1:9090/api/v1/targets | python3 -c '
import json,sys
d=json.load(sys.stdin)
targets=[t for t in d.get("data",{}).get("activeTargets",[]) if t.get("labels",{}).get("job")=="aiops2-twin"]
assert len(targets)==1 and targets[0].get("health")=="up", "Twin target not UP"
' 2>/dev/null; then echo 'PROMETHEUS_TWIN_TARGET=UP'; break; fi
 if [[ "$i" == 30 ]]; then echo 'PROMETHEUS_TWIN_TARGET=NOT_UP'; exit 1; fi
 sleep 3
done
SUCCESS=1
echo "ROLLBACK_CONTAINER_RETAINED=$OLD_NAME"
echo 'PRODUCTION_TWIN_CUTOVER=PASS'
echo 'FS1015_RESULT=PASS'
