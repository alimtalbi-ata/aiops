#!/usr/bin/env bash
# FS1160: deployment preflight; no restart, no secret values, no Portal mutation.
set -euo pipefail
echo "FS1160_MODE=PERMANENT_CORE_GLPI_DEPLOYMENT_PREFLIGHT"
echo "FS1160_MUTATION=NONE"
echo "FS1160_PORTAL_MUTATION=NONE"
CORE=aiops2-rebuild-core
docker inspect -f 'FS1160_CORE_IMAGE={{.Config.Image}}' "$CORE"
docker inspect -f 'FS1160_CORE_ENTRYPOINT={{json .Config.Entrypoint}}' "$CORE"
docker inspect -f 'FS1160_CORE_CMD={{json .Config.Cmd}}' "$CORE"
docker inspect -f 'FS1160_CORE_RESTART={{.HostConfig.RestartPolicy.Name}}' "$CORE"
docker inspect -f 'FS1160_CORE_WORKDIR={{.Config.WorkingDir}}' "$CORE"
docker inspect -f '{{range .Mounts}}FS1160_CORE_MOUNT={{.Destination}} RW={{.RW}}{{println}}{{end}}' "$CORE"
docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}FS1160_CORE_NETWORK={{$k}} IP={{$v.IPAddress}}{{println}}{{end}}' "$CORE"
docker inspect -f 'FS1160_CORE_COMPOSE_PROJECT={{index .Config.Labels "com.docker.compose.project"}}' "$CORE"
docker inspect -f 'FS1160_CORE_COMPOSE_SERVICE={{index .Config.Labels "com.docker.compose.service"}}' "$CORE"
docker inspect -f 'FS1160_CORE_COMPOSE_CONFIG_FILES={{index .Config.Labels "com.docker.compose.project.config_files"}}' "$CORE"
docker exec "$CORE" python -c '
import os,importlib.util,json
for k in ("AIOPS_GLPI_URL","AIOPS_GLPI_APP_TOKEN","AIOPS_GLPI_USER_TOKEN","AIOPS_GLPI_TICKETS_REQUIRED"):
 print("FS1160_ENV_PRESENT_"+k+"="+str(bool(os.getenv(k))).lower())
for k in ("core.glpi_client","core.glpi_ingest","core.glpi_kpi"):
 try:
  spec=importlib.util.find_spec(k)
  print("FS1160_MODULE_"+k+"="+str(bool(spec)).lower())
 except (ImportError,ModuleNotFoundError):
  print("FS1160_MODULE_"+k+"=false")
'
echo "FS1160_COMPOSE_FILES_EXISTENCE"
docker inspect -f '{{index .Config.Labels "com.docker.compose.project.config_files"}}' "$CORE" |
tr ',' '\n' | while IFS= read -r path; do
 if test -f "$path"; then echo "FS1160_COMPOSE_FILE_PRESENT=$path"; else echo "FS1160_COMPOSE_FILE_MISSING=$path"; fi
done
echo "FS1160_CORE_API_ROUTE_PROBE"
docker exec "$CORE" python -c '
import urllib.request,json
for path in ("/openapi.json","/api/kpi/glpi"):
 try:
  with urllib.request.urlopen("http://127.0.0.1:810"+path,timeout=3) as r:
   data=json.load(r)
   if path=="/openapi.json":print("FS1160_ROUTE_KPI_PRESENT="+str("/api/kpi/glpi" in data.get("paths",{})).lower())
   else:print("FS1160_KPI_RESPONSE_SOURCE="+str(data.get("source","unknown")))
 except Exception as e:print("FS1160_ROUTE_PROBE_UNAVAILABLE="+path+" "+type(e).__name__)
'
echo "FS1160_FINAL_STATUS=READ_ONLY_COMPLETE"
