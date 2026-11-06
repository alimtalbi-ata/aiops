#!/usr/bin/env bash
set -euo pipefail
echo "FS1054_MODE=READ_ONLY_POST_ROLLBACK_DIAGNOSTIC"
python3 - <<'PY'
import json,subprocess,urllib.request,urllib.error
def docker(*args):
 p=subprocess.run(["docker",*args],capture_output=True,text=True)
 return p.returncode,p.stdout,p.stderr
rc,out,err=docker("inspect","aiops2-rebuild-portal")
if rc:
 print("FS1054_PROD_INSPECT=FAIL")
 raise SystemExit(1)
o=json.loads(out)[0]
print("FS1054_PROD_IMAGE="+str(o["Config"]["Image"]))
print("FS1054_PROD_RUNNING="+str(o["State"]["Running"]).lower())
print("FS1054_PROD_RESTART="+str(o["HostConfig"].get("RestartPolicy",{}).get("Name")))
print("FS1054_PROD_PORTS="+",".join(sorted((o["NetworkSettings"].get("Ports") or {}).keys())))
print("FS1054_PROD_NETWORKS="+",".join(sorted(o["NetworkSettings"]["Networks"])))
print("FS1054_PROD_MOUNTS="+",".join(sorted(m["Destination"] for m in o["Mounts"])))
for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog"):
 try:
  with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=5) as r:
   status=r.status
 except urllib.error.HTTPError as e: status=e.code
 except Exception as e: status=type(e).__name__
 print("FS1054_PROD_HTTP="+path+" STATUS="+str(status))
rc,out,err=docker("ps","-a","--filter","name=aiops2-rebuild-portal","--format","{{.Names}}|{{.Image}}|{{.Status}}")
print("FS1054_CONTAINERS_BEGIN")
for line in out.splitlines():
 print("FS1054_CONTAINER="+line[:240])
print("FS1054_CONTAINERS_END")
# Do not dump logs: they may contain secrets. Summarize non-sensitive event types.
rc,out,err=docker("inspect","aiops2-rebuild-portal-fs1053-rollback-20261106-230029")
print("FS1054_ROLLBACK_CONTAINER_PRESENT="+str(rc==0).lower())
rc,out,err=docker("image","inspect","aiops2-portal:fs1051-visual-candidate")
print("FS1054_CANDIDATE_IMAGE_PRESENT="+str(rc==0).lower())
PY
