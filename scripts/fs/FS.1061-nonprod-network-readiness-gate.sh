#!/usr/bin/env bash
set -euo pipefail
echo "FS1061_MODE=NONPROD_NETWORK_READINESS_GATE"
python3 - <<'PY'
import json,os,socket,subprocess,tempfile,time,urllib.request,urllib.error
NAME="aiops2-fs1061-gate"
IMAGE="aiops2-portal:fs1051-visual-candidate"
def d(*args,check=True):
 p=subprocess.run(["docker",*args],capture_output=True,text=True)
 if check and p.returncode: raise RuntimeError("docker "+args[0]+" failed: "+p.stderr[-200:])
 return p
assert d("inspect",NAME,check=False).returncode!=0,"FS1061_NAME_OCCUPIED"
prod=json.loads(d("inspect","aiops2-rebuild-portal").stdout)[0]
assert prod["State"]["Running"] and prod["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
d("image","inspect",IMAGE)
for n in ("aiops2-rebuild-integration","aiops2-rebuild-control","aiops2-rebuild-public"): d("network","inspect",n)
with socket.socket() as sk:
 sk.bind(("127.0.0.1",0))
 port=sk.getsockname()[1]
fd,envpath=tempfile.mkstemp(prefix="fs1061-env-",dir="/tmp",text=True)
os.fchmod(fd,0o600)
created=False
try:
 with os.fdopen(fd,"w") as f:
  for item in prod["Config"].get("Env",[]):
   assert "\n" not in item and "\r" not in item
   f.write(item+"\n")
 d("run","-d","--name",NAME,"--network","aiops2-rebuild-integration",
   "-p","127.0.0.1:"+str(port)+":777","--env-file",envpath,
   "--read-only","--tmpfs","/tmp:rw,nosuid,size=32m",
   "--cap-drop","ALL","--security-opt","no-new-privileges",IMAGE)
 created=True
 d("network","connect","aiops2-rebuild-control",NAME)
 d("network","connect","aiops2-rebuild-public",NAME)
 print("FS1061_ALL_NETWORKS_CONNECTED=YES",flush=True)
 ready=False
 for attempt in range(1,41):
  obj=json.loads(d("inspect",NAME).stdout)[0]
  assert obj["State"]["Running"],"candidate exited"
  nets=set(obj["NetworkSettings"]["Networks"])
  expected={"aiops2-rebuild-integration","aiops2-rebuild-control","aiops2-rebuild-public"}
  mapping=(obj["NetworkSettings"].get("Ports") or {}).get("777/tcp") or []
  bound=any(p.get("HostPort")==str(port) and p.get("HostIp")=="127.0.0.1" for p in mapping)
  if nets==expected and bound:
   try:
    with urllib.request.urlopen("http://127.0.0.1:"+str(port)+"/health",timeout=2) as r:
     if r.status==200:
      ready=True
      print("FS1061_READY_ATTEMPT="+str(attempt),flush=True)
      break
   except (urllib.error.URLError,TimeoutError,ConnectionError,OSError):
    pass
  time.sleep(1)
 assert ready,"FS1061_NETWORK_HTTP_READINESS_TIMEOUT"
 print("FS1061_NETWORK_GATE=PASS",flush=True)
 for endpoint in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
  with urllib.request.urlopen("http://127.0.0.1:"+str(port)+endpoint,timeout=5) as r: status=r.status
  print("FS1061_HOST_HTTP="+endpoint+" STATUS="+str(status),flush=True)
  assert status==200
 print("FS1061_RESULT=PASS",flush=True)
finally:
 os.unlink(envpath)
 if created:
  d("rm","-f",NAME,check=False)
  print("FS1061_TEMP_CONTAINER=REMOVED",flush=True)
PY
