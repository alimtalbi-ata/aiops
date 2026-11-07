#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
echo "FS1115_MODE=CLOUDBEAVER_DATABASE_DISCOVERY_READ_ONLY"
docker inspect "$CB" --format 'CLOUDBEAVER_STATUS={{.State.Status}} CLOUDBEAVER_IMAGE={{.Config.Image}}'
docker inspect aiops2-rebuild-portal --format 'PORTAL_IMAGE={{.Config.Image}} PORTAL_STATUS={{.State.Status}}'
python3 - <<'PY'
import json,subprocess,re
def docker(*args):
    return subprocess.check_output(["docker",*args],text=True)
ids=docker("ps","-q").split()
if not ids:
    print("FS1115_NO_RUNNING_CONTAINERS");raise SystemExit(0)
items=json.loads(docker("inspect",*ids))
cb=next((c for c in items if c["Name"].lstrip("/")== "aiops2-rebuild-cloudbeaver"),None)
cbnets=set((cb or {}).get("NetworkSettings",{}).get("Networks",{}))
print("FS1115_CLOUDBEAVER_NETWORKS="+",".join(sorted(cbnets)))
for c in sorted(items,key=lambda x:x["Name"]):
    name=c["Name"].lstrip("/")
    image=c["Config"]["Image"]
    networks=set(c.get("NetworkSettings",{}).get("Networks",{}))
    ports=c["Config"].get("ExposedPorts") or {}
    image_l=image.lower()
    role=("postgres" if re.search(r"postgres|timescale|postgis",image_l+" "+name.lower()) else
          "mariadb/mysql" if re.search(r"mariadb|mysql",image_l+" "+name.lower()) else
          "database_candidate" if re.search(r"database|db|glpi|temporal|core",name.lower()) else None)
    if not role:continue
    shared=sorted(cbnets & networks)
    exposed=sorted(ports)
    print("FS1115_DATABASE name=%s role=%s image=%s exposed=%s shared_networks=%s networks=%s" % (
        name,role,image,",".join(exposed) or "unknown",",".join(shared) or "NONE",",".join(sorted(networks)) or "NONE"))
print("FS1115_DISCOVERY_COMPLETE=YES")
print("FS1115_SECRETS_PRINTED=NO")
print("FS1115_CHANGES=NONE")
PY
