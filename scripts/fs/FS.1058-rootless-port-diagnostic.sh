#!/usr/bin/env bash
set -euo pipefail
echo "FS1058_MODE=ISOLATED_ROOTLESS_PORT_DIAGNOSTIC"
python3 - <<'PY'
import json,os,socket,subprocess,tempfile,time,urllib.error,urllib.request
NAME="aiops2-fs1058-portdiag"
IMAGE="aiops2-portal:fs1051-visual-candidate"
def docker(*args,check=True):
 p=subprocess.run(["docker",*args],capture_output=True,text=True)
 if check and p.returncode: raise RuntimeError("docker "+args[0]+" failed (exit="+str(p.returncode)+")")
 return p
assert docker("inspect",NAME,check=False).returncode!=0,"test container name occupied"
prod=json.loads(docker("inspect","aiops2-rebuild-portal").stdout)[0]
assert prod["State"]["Running"] and prod["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
docker("image","inspect",IMAGE)
with socket.socket() as sock:
 sock.bind(("127.0.0.1",0))
 port=sock.getsockname()[1]
print("FS1058_SELECTED_PORT="+str(port),flush=True)
fd,path=tempfile.mkstemp(prefix="fs1058-env-",dir="/tmp",text=True)
os.fchmod(fd,0o600)
created=False
try:
 with os.fdopen(fd,"w") as f:
  for item in prod["Config"].get("Env",[]):
   assert "\n" not in item and "\r" not in item
   f.write(item+"\n")
 docker("run","-d","--name",NAME,"--network","aiops2-rebuild-integration",
        "-p","127.0.0.1:"+str(port)+":777","--env-file",path,
        "--read-only","--tmpfs","/tmp:rw,nosuid,size=32m",
        "--cap-drop","ALL","--security-opt","no-new-privileges",IMAGE)
 created=True
 docker("network","connect","aiops2-rebuild-control",NAME)
 print("FS1058_TEMP_CONTAINER=STARTED",flush=True)
 for attempt in range(1,11):
  state=json.loads(docker("inspect",NAME).stdout)[0]
  print("FS1058_ATTEMPT="+str(attempt)+" RUNNING="+str(state["State"]["Running"]).lower()+
        " EXIT="+str(state["State"].get("ExitCode"))+" RESTARTS="+str(state.get("RestartCount",0)),flush=True)
  portmap=state["NetworkSettings"].get("Ports",{}).get("777/tcp")
  print("FS1058_DOCKER_PORT_MAP="+str(portmap),flush=True)
  p=docker("exec",NAME,"python","-c",
     "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:777/health',timeout=2).status)",
     check=False)
  print("FS1058_INSIDE_HTTP="+(p.stdout.strip() if p.returncode==0 else "FAILED"),flush=True)
  try:
   with urllib.request.urlopen("http://127.0.0.1:"+str(port)+"/health",timeout=3) as r:
    print("FS1058_HOST_HTTP="+str(r.status),flush=True)
    if r.status==200:
     print("FS1058_HOST_PORT=PASS",flush=True)
     break
  except Exception as e:
   detail=str(getattr(e,"reason",e))
   print("FS1058_HOST_ERROR="+type(e).__name__+" DETAIL="+detail[:160],flush=True)
  time.sleep(2)
 else:
  print("FS1058_HOST_PORT=FAIL",flush=True)
 print("FS1058_PRODUCTION_UNCHANGED=YES",flush=True)
finally:
 os.unlink(path)
 if created:
  docker("rm","-f",NAME,check=False)
  print("FS1058_TEMP_CONTAINER=REMOVED",flush=True)
PY
