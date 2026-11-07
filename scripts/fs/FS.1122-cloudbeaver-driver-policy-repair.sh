#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
VOL=aiops2-cloudbeaver-workspace
echo "FS1122_MODE=SAFE_DRIVER_POLICY_REPAIR"
echo "FS1122_SQL_MUTATION=NONE"
echo "FS1122_PORTAL_MUTATION=NONE"
docker inspect "$CB" --format '{{.State.Running}}' | grep -Fx true >/dev/null
docker run --rm -i --mount "type=volume,source=$VOL,target=/workspace" python:3.12-alpine python - <<'PY'
import json,pathlib,shutil,datetime
root=pathlib.Path("/workspace")
target={"postgresql:postgres-jdbc","mysql:mariaDB"}
configs=list(root.rglob("*.conf"))
print("FS1122_CONF_FILES="+str(len(configs)))
for p in configs:
 if not p.is_file() or p.stat().st_size>5_000_000:continue
 try: cfg=json.loads(p.read_text())
 except (ValueError,UnicodeError,PermissionError):continue
 found=[]
 def visit(node,path):
  if isinstance(node,dict):
   for k,v in node.items():
    if k in ("enabledDrivers","disabledDrivers") and isinstance(v,list):
     found.append((path,k,v,node))
    else:visit(v,path+"."+k)
  elif isinstance(node,list):
   for i,v in enumerate(node):visit(v,path+"["+str(i)+"]")
 visit(cfg,"$")
 if not found:continue
 print("FS1122_POLICY_FILE="+str(p.relative_to(root)))
 for location,key,values,_ in found:
  relevant=sorted(target.intersection(v for v in values if isinstance(v,str)))
  print("FS1122_POLICY="+location+"."+key+" count="+str(len(values))+" targeted="+",".join(relevant or ["none"]))
 # Only modify explicit allow/deny settings; never broaden permissions for other drivers.
 changed=False
 for _,key,values,parent in found:
  if key=="disabledDrivers":
   updated=[v for v in values if v not in target]
   if len(updated)!=len(values):
    parent[key]=updated;changed=True
  if key=="enabledDrivers" and values:
   missing=sorted(target.difference(values))
   if missing:
    parent[key]=values+missing;changed=True
 if changed:
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
  backup=p.with_name(p.name+".fs1122-"+stamp+".bak")
  shutil.copy2(p,backup)
  tmp=p.with_name(p.name+".fs1122.tmp")
  tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n")
  shutil.copymode(p,tmp)
  tmp.replace(p)
  print("FS1122_BACKUP="+str(backup.relative_to(root)))
  print("FS1122_POLICY_UPDATED="+str(p.relative_to(root)))
 else:print("FS1122_POLICY_UNCHANGED="+str(p.relative_to(root)))
PY
echo "FS1122_POLICY_SCAN=COMPLETE"
echo "FS1122_DRIVER_CONFIG_HINTS_BEGIN"
docker exec "$CB" sh -c '
for f in /opt/cloudbeaver/conf/cloudbeaver.conf /opt/cloudbeaver/conf/cloudbeaver.runtime.conf /opt/cloudbeaver/workspace/.data/.cloudbeaver.runtime.conf; do
 if [ -f "$f" ]; then
  echo "FILE=$f"
  grep -nE "enabledDrivers|disabledDrivers" "$f" | cut -c1-180 || true
 fi
done
' || true
echo "FS1122_DRIVER_CONFIG_HINTS_END"
echo "FS1122_RESULT=POLICY_CHECKED"
echo "FS1122_NOTE=RESTART_CLOUDBEAVER_ONLY_IF_POLICY_UPDATED"
