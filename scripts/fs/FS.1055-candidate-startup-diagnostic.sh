#!/usr/bin/env bash
set -euo pipefail
echo "FS1055_MODE=READ_ONLY_CANDIDATE_STARTUP_DIAGNOSTIC"
python3 - <<'PY'
import json, subprocess, urllib.request, urllib.error
def run(*args):
 p=subprocess.run(["docker",*args],capture_output=True,text=True)
 if p.returncode: raise RuntimeError("docker "+args[0]+" failed")
 return p.stdout
prod=json.loads(run("inspect","aiops2-rebuild-portal"))[0]
print("FS1055_PROD_IMAGE="+prod["Config"]["Image"])
print("FS1055_PROD_RUNNING="+str(prod["State"]["Running"]).lower())
print("FS1055_PROD_ENTRYPOINT="+str(prod["Config"].get("Entrypoint")))
print("FS1055_PROD_CMD="+str(prod["Config"].get("Cmd")))
candidate=json.loads(run("image","inspect","aiops2-portal:fs1051-visual-candidate"))[0]
print("FS1055_CANDIDATE_ENTRYPOINT="+str(candidate["Config"].get("Entrypoint")))
print("FS1055_CANDIDATE_CMD="+str(candidate["Config"].get("Cmd")))
print("FS1055_PROD_PORT_BINDINGS="+str(prod["HostConfig"].get("PortBindings")))
print("FS1055_PROD_HEALTHCHECK_DEFINED="+str(bool(prod["Config"].get("Healthcheck"))).lower())
print("FS1055_PROD_RESTART_COUNT="+str(prod.get("RestartCount",0)))
print("FS1055_PROD_NETWORKS="+",".join(sorted(prod["NetworkSettings"]["Networks"])))
# No env values, secrets, or raw container logs are printed.
for path in ("/health","/explorer/visual"):
 try:
  with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=4) as r: code=r.status
 except urllib.error.HTTPError as e: code=e.code
 except Exception as e: code=type(e).__name__
 print("FS1055_CURRENT_HTTP="+path+" STATUS="+str(code))
print("FS1055_DIAGNOSTIC=COMPLETE")
PY
