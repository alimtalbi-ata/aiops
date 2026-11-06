#!/usr/bin/env bash
set -euo pipefail
echo "FS1057_MODE=LOCALHOST_ONLY_HTTP_REPRODUCTION"
python3 - <<'PY'
import http.client,json,os,socket,subprocess,tempfile,time,urllib.error,urllib.request
NAME="aiops2-fs1057-http-test"
IMAGE="aiops2-portal:fs1051-visual-candidate"
PORT=17777
def docker(*args,check=True):
 p=subprocess.run(["docker",*args],capture_output=True,text=True)
 if check and p.returncode: raise RuntimeError("docker "+args[0]+" failed: "+p.stderr[-200:])
 return p
assert docker("inspect",NAME,check=False).returncode!=0,"FS1057_TEST_NAME_OCCUPIED"
prod=json.loads(docker("inspect","aiops2-rebuild-portal").stdout)[0]
assert prod["State"]["Running"] and prod["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
with socket.socket() as sock:
 sock.bind(("127.0.0.1",PORT))
docker("image","inspect",IMAGE)
for network in ("aiops2-rebuild-integration","aiops2-rebuild-control"): docker("network","inspect",network)
fd,path=tempfile.mkstemp(prefix="fs1057-env-",dir="/tmp",text=True)
os.fchmod(fd,0o600)
created=False
try:
 with os.fdopen(fd,"w") as f:
  for item in prod["Config"].get("Env",[]):
   assert "\n" not in item and "\r" not in item
   f.write(item+"\n")
 docker("run","-d","--name",NAME,"--network","aiops2-rebuild-integration",
        "-p","127.0.0.1:"+str(PORT)+":777","--env-file",path,
        "--read-only","--tmpfs","/tmp:rw,nosuid,size=32m",
        "--cap-drop","ALL","--security-opt","no-new-privileges",IMAGE)
 created=True
 docker("network","connect","aiops2-rebuild-control",NAME)
 print("FS1057_TEMP_CONTAINER=STARTED",flush=True)
 paths=("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual")
 for endpoint in paths:
  status=None
  for attempt in range(30):
   try:
    with urllib.request.urlopen("http://127.0.0.1:"+str(PORT)+endpoint,timeout=3) as r:
     status=r.status
    if status==200: break
   except (urllib.error.URLError,http.client.RemoteDisconnected,ConnectionError,TimeoutError,OSError) as exc:
    status=type(exc).__name__
   time.sleep(1)
  print("FS1057_HOST_HTTP="+endpoint+" STATUS="+str(status),flush=True)
  assert status==200,"HTTP probe failed: "+endpoint
 state=json.loads(docker("inspect",NAME).stdout)[0]
 print("FS1057_RESTART_COUNT="+str(state.get("RestartCount",0)))
 assert state["State"]["Running"] and state.get("RestartCount",0)==0
 print("FS1057_RESULT=PASS",flush=True)
finally:
 os.unlink(path)
 if created:
  docker("rm","-f",NAME,check=False)
  print("FS1057_TEMP_CONTAINER=REMOVED",flush=True)
PY
