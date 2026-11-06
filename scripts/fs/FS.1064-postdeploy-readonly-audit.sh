#!/usr/bin/env bash
set -euo pipefail
echo "FS1064_MODE=READ_ONLY_POST_DEPLOY_AUDIT"
python3 - <<'PY'
import json,subprocess,urllib.request,urllib.error
def docker(*args):
 p=subprocess.run(["docker",*args],capture_output=True,text=True,check=True)
 return p.stdout
obj=json.loads(docker("inspect","aiops2-rebuild-portal"))[0]
assert obj["State"]["Running"],"portal not running"
assert obj["Config"]["Image"]=="aiops2-portal:fs1051-visual-candidate","wrong image"
assert obj["HostConfig"]["RestartPolicy"]["Name"]=="unless-stopped"
expected={"aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public"}
assert set(obj["NetworkSettings"]["Networks"])==expected
mapping=(obj["NetworkSettings"].get("Ports") or {}).get("777/tcp") or []
assert any(p.get("HostPort")=="7777" for p in mapping)
assert obj.get("RestartCount",0)==0,"unexpected restart"
print("FS1064_IMAGE="+obj["Config"]["Image"])
print("FS1064_NETWORKS="+",".join(sorted(expected)))
print("FS1064_RESTARTS="+str(obj.get("RestartCount",0)))
print("FS1064_MOUNTS="+str(len(obj.get("Mounts",[]))))
assert len(obj.get("Mounts",[]))>=2
for path in ("/health","/explorer/databases","/explorer/prometheus","/explorer/cmdb","/api/explorer/catalog","/explorer/visual"):
 with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=6) as r:
  assert r.status==200,(path,r.status)
 print("FS1064_HTTP="+path+" STATUS=200")
for path in ("/api/fs1051/prometheus","/api/fs1051/twin"):
 try:
  with urllib.request.urlopen("http://127.0.0.1:7777"+path,timeout=12) as r:
   data=json.loads(r.read(2000000))
   assert r.status==200
   print("FS1064_API="+path+" STATUS=200 KEYS="+",".join(sorted(data.keys())[:12]))
 except urllib.error.HTTPError as exc:
  print("FS1064_API="+path+" STATUS="+str(exc.code))
  raise
print("FS1064_RESULT=PASS")
PY
