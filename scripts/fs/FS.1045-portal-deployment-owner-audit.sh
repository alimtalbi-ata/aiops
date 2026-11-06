#!/usr/bin/env bash
# FS.1045 — non-invasive deployment ownership discovery.
set -euo pipefail
TARGET=aiops2-rebuild-portal
echo "FS1045_MODE=READ_ONLY_DEPLOYMENT_DISCOVERY"
docker inspect "$TARGET" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]
c=d.get("Config") or {}
h=d.get("HostConfig") or {}
l=c.get("Labels") or {}
n=d.get("NetworkSettings") or {}
print("CONTAINER_NAME="+d.get("Name",""))
print("CONTAINER_STATUS="+str((d.get("State") or {}).get("Status")))
print("IMAGE_TAG="+str(c.get("Image")))
print("IMAGE_ID="+str(d.get("Image")))
print("RESTART_POLICY="+str((h.get("RestartPolicy") or {}).get("Name")))
print("NETWORK_MODE="+str(h.get("NetworkMode")))
print("NETWORK_NAMES="+",".join(sorted((n.get("Networks") or {}).keys())))
print("MOUNT_TYPES="+",".join(sorted(set(str(m.get("Type")) for m in d.get("Mounts") or []))))
print("PUBLISHED_PORTS="+",".join(sorted((h.get("PortBindings") or {}).keys())))
for key in ("com.docker.compose.project","com.docker.compose.service","com.docker.compose.project.working_dir","com.docker.compose.project.config_files","com.docker.compose.version"):
 print("COMPOSE_LABEL_"+key.split(".")[-1].upper()+"_PRESENT="+str(bool(l.get(key))))
print("LABEL_NAMES="+",".join(sorted(l)))
print("ENV_KEY_NAMES="+",".join(sorted(set(v.split("=",1)[0] for v in c.get("Env") or []))))
'
echo "===== ROOTLESS DOCKER CONTEXT ====="
docker context show
echo "===== SYSTEMD USER SERVICE NAMES (FILTERED) ====="
systemctl --user list-unit-files --no-legend 2>/dev/null | awk 'tolower($1) ~ /aiops|portal|rebuild/ {print $1}' || true
echo "===== HOST CONFIG FILE PATHS (NAMES ONLY) ====="
find /home/aiops -maxdepth 4 -type f \( -iname '*compose*.yml' -o -iname '*compose*.yaml' -o -iname '*portal*.service' \) -print 2>/dev/null | head -80
echo "FS1045_DISCOVERY=COMPLETE"
