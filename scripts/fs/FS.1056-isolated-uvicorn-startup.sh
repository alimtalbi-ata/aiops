#!/usr/bin/env bash
set -euo pipefail
echo "FS1056_MODE=ISOLATED_REAL_UVICORN_STARTUP"
python3 - <<'PY'
import json,os,subprocess,tempfile,time
NAME="aiops2-fs1056-startup"
IMAGE="aiops2-portal:fs1051-visual-candidate"
def docker(*args,check=True):
 p=subprocess.run(["docker",*args],text=True,capture_output=True)
 if check and p.returncode: raise RuntimeError("docker "+args[0]+" failed (exit "+str(p.returncode)+")")
 return p
if docker("container","inspect",NAME,check=False).returncode==0:
 raise SystemExit("FS1056_ABORT=TEST_CONTAINER_ALREADY_EXISTS")
prod=json.loads(docker("inspect","aiops2-rebuild-portal").stdout)[0]
assert prod["State"]["Running"] and prod["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
docker("image","inspect",IMAGE)
docker("network","inspect","aiops2-rebuild-integration")
docker("network","inspect","aiops2-rebuild-control")
fd,path=tempfile.mkstemp(prefix="fs1056-env-",dir="/tmp",text=True)
os.fchmod(fd,0o600)
created=False
try:
 with os.fdopen(fd,"w") as f:
  for env in prod["Config"].get("Env",[]):
   assert "\n" not in env and "\r" not in env
   f.write(env+"\n")
 args=["run","-d","--name",NAME,"--network","aiops2-rebuild-integration",
       "--env-file",path,"--read-only","--tmpfs","/tmp:rw,nosuid,size=32m",
       "--cap-drop","ALL","--security-opt","no-new-privileges",IMAGE]
 docker(*args)
 created=True
 docker("network","connect","aiops2-rebuild-control",NAME)
 print("FS1056_TEMP_CONTAINER=STARTED",flush=True)
 code=r'''import urllib.request,urllib.error
for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
 try:
  with urllib.request.urlopen("http://127.0.0.1:777"+path,timeout=3) as r: status=r.status
 except urllib.error.HTTPError as e: status=e.code
 except Exception as e: status=type(e).__name__
 print(path+"="+str(status))
'''
 healthy=False
 for i in range(20):
  state=json.loads(docker("inspect",NAME).stdout)[0]["State"]
  if not state["Running"]:
   print("FS1056_CONTAINER_EXIT_CODE="+str(state.get("ExitCode")))
   break
  p=docker("exec",NAME,"python","-c",code,check=False)
  if p.returncode==0 and "/health=200" in p.stdout and "/explorer/visual=200" in p.stdout:
   for line in p.stdout.splitlines(): print("FS1056_HTTP="+line)
   healthy=True
   break
  time.sleep(1)
 print("FS1056_STARTUP="+("PASS" if healthy else "FAIL"))
 print("FS1056_RESTART_COUNT="+str(json.loads(docker("inspect",NAME).stdout)[0].get("RestartCount",0)))
 if not healthy: raise SystemExit(1)
finally:
 try: os.unlink(path)
 except FileNotFoundError: pass
 if created:
  docker("rm","-f",NAME,check=False)
  print("FS1056_TEMP_CONTAINER=REMOVED",flush=True)
PY
