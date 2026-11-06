#!/usr/bin/env bash
set -euo pipefail
echo "FS1059_MODE=ISOLATED_PORT_BINDING_TRANSITIONS"
python3 - <<'PY'
import json,os,socket,subprocess,tempfile,time,urllib.request
name="aiops2-fs1059-netdiag"
image="aiops2-portal:fs1051-visual-candidate"
def d(*args,check=True):
 p=subprocess.run(["docker",*args],capture_output=True,text=True)
 if check and p.returncode: raise RuntimeError("docker "+args[0]+" failed: "+p.stderr[-180:])
 return p
assert d("inspect",name,check=False).returncode!=0,"FS1059_NAME_BUSY"
prod=json.loads(d("inspect","aiops2-rebuild-portal").stdout)[0]
assert prod["State"]["Running"] and prod["Config"]["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
with socket.socket() as sock:
 sock.bind(("127.0.0.1",0))
 port=sock.getsockname()[1]
print("FS1059_PORT="+str(port),flush=True)
fd,path=tempfile.mkstemp(prefix="fs1059-env-",dir="/tmp",text=True)
os.fchmod(fd,0o600)
created=False
def inspect_phase(label):
 obj=json.loads(d("inspect",name).stdout)[0]
 host=obj["HostConfig"].get("PortBindings") or {}
 net=obj["NetworkSettings"].get("Ports") or {}
 print("FS1059_"+label+"_HOSTCONFIG="+str(host.get("777/tcp")),flush=True)
 print("FS1059_"+label+"_NETWORK_PORTS="+str(net.get("777/tcp")),flush=True)
 print("FS1059_"+label+"_NETWORKS="+",".join(sorted(obj["NetworkSettings"]["Networks"])),flush=True)
 print("FS1059_"+label+"_RUNNING="+str(obj["State"]["Running"]).lower(),flush=True)
def hostprobe(label):
 try:
  with urllib.request.urlopen("http://127.0.0.1:"+str(port)+"/health",timeout=3) as r: result=str(r.status)
 except Exception as exc: result=type(exc).__name__+":"+str(getattr(exc,"reason",exc))[:80]
 print("FS1059_"+label+"_HTTP="+result,flush=True)
try:
 with os.fdopen(fd,"w") as f:
  for item in prod["Config"].get("Env",[]):
   assert "\n" not in item and "\r" not in item
   f.write(item+"\n")
 d("run","-d","--name",name,"--network","aiops2-rebuild-integration",
   "-p","127.0.0.1:"+str(port)+":777","--env-file",path,
   "--read-only","--tmpfs","/tmp:rw,nosuid,size=32m",
   "--cap-drop","ALL","--security-opt","no-new-privileges",image)
 created=True
 for _ in range(10):
  p=d("exec",name,"python","-c","import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:777/health',timeout=2).status)",check=False)
  if p.returncode==0: break
  time.sleep(1)
 print("FS1059_INSIDE_HEALTH="+("200" if p.returncode==0 else "FAIL"),flush=True)
 inspect_phase("INITIAL")
 hostprobe("INITIAL")
 d("network","connect","aiops2-rebuild-control",name)
 inspect_phase("AFTER_CONTROL")
 hostprobe("AFTER_CONTROL")
 d("network","connect","aiops2-rebuild-public",name)
 inspect_phase("AFTER_PUBLIC")
 hostprobe("AFTER_PUBLIC")
 print("FS1059_RESULT=COMPLETE",flush=True)
finally:
 os.unlink(path)
 if created:
  d("rm","-f",name,check=False)
  print("FS1059_TEMP_CONTAINER=REMOVED",flush=True)
PY
