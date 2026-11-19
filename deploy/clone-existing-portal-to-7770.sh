#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
SOURCE="\${AIOPS_PORTAL_SOURCE:-aiops2-rebuild-portal}"
CANDIDATE="\${AIOPS_PORTAL_CANDIDATE:-aiops2-portal-7770-candidate}"
PORT="\${AIOPS_PORTAL_TARGET_PORT:-7770}"
SNAP="/tmp/aiops2-portal-clone-$$.json"
trap 'rm -f "$SNAP"' EXIT
fail(){ echo "FAIL|$1"; exit 1; }
docker inspect "$SOURCE" > "$SNAP" 2>/dev/null || fail "source_missing"
[[ "$(docker inspect -f '{{.State.Running}}' "$SOURCE")" == true ]] || fail "source_not_running"
docker inspect "$CANDIDATE" >/dev/null 2>&1 && fail "candidate_exists_inspect_first"
ss -ltnH "sport = :$PORT" | grep -q . && fail "target_port_in_use"
python3 - "$SNAP" "$CANDIDATE" "$PORT" <<'PY'
import json,subprocess,sys
snap,name,port=sys.argv[1:]
c=json.load(open(snap))[0]; cfg=c["Config"]; host=c["HostConfig"]
assert c["State"]["Running"] and c["Image"] and cfg["Cmd"] is not None
mounts=c.get("Mounts") or []; nets=list(c["NetworkSettings"]["Networks"])
assert mounts and len(nets)>=1
args=["docker","create","--name",name,"--publish",f"0.0.0.0:{port}:777"]
rp=host.get("RestartPolicy") or {}
if rp.get("Name") and rp["Name"]!="no":
    value=rp["Name"]
    if rp.get("MaximumRetryCount"): value+=":"+str(rp["MaximumRetryCount"])
    args+=["--restart",value]
for key,opt in [("User","--user"),("WorkingDir","--workdir"),("Hostname","--hostname"),("StopSignal","--stop-signal")]:
    if cfg.get(key): args += [opt,cfg[key]]
for item in cfg.get("Env") or []: args += ["--env",item]
for m in mounts:
    source=m["Name"] if m["Type"]=="volume" else m["Source"]
    spec=f"type={m['Type']},source={source},target={m['Destination']}"
    if not m.get("RW",True): spec+=",readonly"
    args += ["--mount",spec]
args += ["--network",nets[0]]
entry=cfg.get("Entrypoint")
if entry: args += ["--entrypoint",entry[0]]
args += [c["Image"]]
if entry and len(entry)>1: args += entry[1:]
args += cfg.get("Cmd") or []
subprocess.run(args,check=True)
for network in nets[1:]:
    subprocess.run(["docker","network","connect",network,name],check=True)
print("IMAGE_DIGEST="+c["Image"])
print("NETWORK_COUNT="+str(len(nets)))
print("MOUNT_COUNT="+str(len(mounts)))
print("ENV_COUNT="+str(len(cfg.get("Env") or [])))
PY
echo "===== START NON-DISRUPTIVE CANDIDATE ====="
docker start "$CANDIDATE" >/dev/null
ok=0
for i in $(seq 1 40); do
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/" -o /dev/null; then ok=1; break; fi
  sleep 1
done
if [[ "$ok" != 1 ]]; then
  echo "CANDIDATE_HTTP_FAILED=true"
  docker logs --tail 50 "$CANDIDATE" 2>&1 | sed -E 's/(TOKEN|SECRET|PASSWORD|KEY)=([^ ]+)/\1=[REDACTED]/Ig'
  docker rm -f "$CANDIDATE" >/dev/null
  fail "candidate_failed_source_untouched"
fi
echo "SOURCE_STILL_RUNNING=$(docker inspect -f '{{.State.Running}}' "$SOURCE")"
echo "SOURCE_IMAGE=$(docker inspect -f '{{.Image}}' "$SOURCE")"
echo "CANDIDATE_IMAGE=$(docker inspect -f '{{.Image}}' "$CANDIDATE")"
echo "CANDIDATE_PORT=$PORT"
echo "CANDIDATE_HTTP=200"
echo "SOURCE_PORT=7777_UNCHANGED"
echo "NO_BUILD=true"
echo "NO_SOURCE_STOP=true"
