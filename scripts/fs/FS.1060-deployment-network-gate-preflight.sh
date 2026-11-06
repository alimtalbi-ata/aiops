#!/usr/bin/env bash
set -euo pipefail
echo "FS1060_MODE=READ_ONLY_DEPLOYMENT_GATE_REVIEW"
python3 - <<'PY'
import json,subprocess
def cmd(*args):
 p=subprocess.run(["docker",*args],capture_output=True,text=True,check=True)
 return p.stdout
prod=json.loads(cmd("inspect","aiops2-rebuild-portal"))[0]
assert prod["State"]["Running"]
assert prod["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
net=prod["NetworkSettings"]["Networks"]
assert set(net)=={"aiops2-rebuild-integration","aiops2-rebuild-control","aiops2-rebuild-public"}
binding=(prod["NetworkSettings"].get("Ports") or {}).get("777/tcp")
print("FS1060_PRODUCTION_NETWORKS="+",".join(sorted(net)))
print("FS1060_PRODUCTION_EFFECTIVE_PORT="+str(binding))
assert binding and any(b.get("HostPort")=="7777" for b in binding)
print("FS1060_PRODUCTION=PASS")
print("FS1060_NEXT_DEPLOY_GATE=WAIT_FOR_EFFECTIVE_NETWORK_PORT_BINDING_BEFORE_HTTP")
print("FS1060_RESULT=PASS")
PY
