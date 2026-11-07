#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
VOL=aiops2-cloudbeaver-workspace
echo "FS1117_MODE=CLOUDBEAVER_DRIVER_CONFIG_REPAIR"
echo "FS1117_SQL_MUTATION=NONE"
echo "FS1117_PORTAL_MUTATION=NONE"
docker inspect "$CB" --format '{{.State.Running}}' | grep -Fx true >/dev/null
docker volume inspect "$VOL" >/dev/null
docker run --rm -i --mount "type=volume,source=$VOL,target=/workspace" python:3.12-alpine python - <<'PY'
import json,pathlib,shutil,datetime
p=pathlib.Path("/workspace/GlobalConfiguration/.dbeaver/data-sources.json")
if not p.is_file():raise SystemExit("FS1117_ERROR=DATA_SOURCES_MISSING")
cfg=json.loads(p.read_text())
connections=cfg.get("connections",{})
for key in ("aiops2-core","aiops2-temporal","aiops2-glpi"):
    if key not in connections:raise SystemExit("FS1117_ERROR=MISSING_CONNECTION_"+key)
for key in ("aiops2-core","aiops2-temporal"):
    driver=connections[key].get("driver")
    if driver!="postgresql":raise SystemExit("FS1117_ERROR=UNEXPECTED_POSTGRES_DRIVER_"+str(driver))
glpi=connections["aiops2-glpi"]
if glpi.get("driver") not in ("mysql","mariaDB"):
    raise SystemExit("FS1117_ERROR=UNEXPECTED_GLPI_DRIVER_"+str(glpi.get("driver")))
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup=p.with_name(p.name+".fs1117-"+stamp+".bak")
shutil.copy2(p,backup)
glpi["driver"]="mariaDB"
tmp=p.with_name(p.name+".fs1117.tmp")
tmp.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+"\n")
tmp.replace(p)
print("FS1117_BACKUP="+backup.name)
print("FS1117_GLPI_DRIVER=mariaDB")
print("FS1117_CONNECTIONS="+str(len(connections)))
print("FS1117_CONFIG=WRITTEN")
PY
echo "FS1117_RESTART=CLOUDBEAVER_ONLY"
docker restart "$CB" >/dev/null
ready=NO
for attempt in $(seq 1 60); do
  code="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ 2>/dev/null || true)"
  if [[ "$code" == 200 ]];then ready=YES;break;fi
  sleep 2
done
echo "FS1117_HTTP_READY=$ready"
[[ "$ready" == YES ]] || exit 1
echo "FS1117_RELEVANT_LOGS_BEGIN"
docker logs --since 3m "$CB" 2>&1 | grep -Ei 'DataSourceSerializer|driver mysql|driver mariaDB|AccessDenied|started oejs' | tail -20 || true
echo "FS1117_RELEVANT_LOGS_END"
echo "FS1117_RESULT=CONFIG_REPAIR_APPLIED_VERIFY_UI"
