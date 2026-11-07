#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
VOL=aiops2-cloudbeaver-workspace
echo "FS1121_MODE=DOCUMENTED_CLOUDBEAVER_PRECONFIGURED_CONNECTIONS"
echo "FS1121_PASSWORDS=NOT_STORED"
echo "FS1121_SQL_MUTATION=NONE"
echo "FS1121_PORTAL_MUTATION=NONE"
docker inspect "$CB" --format '{{.State.Running}}' | grep -Fx true >/dev/null
docker run --rm -i --mount "type=volume,source=$VOL,target=/workspace" python:3.12-alpine python - <<'PY'
import json,pathlib,shutil,datetime
p=pathlib.Path("/workspace/GlobalConfiguration/.dbeaver/data-sources.json")
cfg=json.loads(p.read_text())
connections=cfg.setdefault("connections",{})
definitions={
 "aiops2-core":("AIOps2 - Core","postgresql","postgres-jdbc","aiops2-rebuild-postgres","5432","aiops"),
 "aiops2-temporal":("AIOps2 - Temporal","postgresql","postgres-jdbc","aiops2-rebuild-temporal-postgres","5432","temporal"),
 "aiops2-glpi":("AIOps2 - GLPI","mysql","mariaDB","aiops2-rebuild-glpi-db","3306","glpi"),
}
for key,(name,provider,driver,host,port,database) in definitions.items():
 if key in connections:
  raise SystemExit("FS1121_REFUSE_EXISTING_CONNECTION="+key)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup=p.with_name(p.name+".fs1121-"+stamp+".bak")
shutil.copy2(p,backup)
for key,(name,provider,driver,host,port,database) in definitions.items():
 connections[key]={
  "provider":provider,"driver":driver,"name":name,
  "save-password":False,
  "configuration":{
   "host":host,"port":port,"database":database,
   "configurationType":"MANUAL","auth-model":"native"
  }
 }
 print("FS1121_ADDED="+name+" DRIVER="+provider+":"+driver)
tmp=p.with_name(p.name+".fs1121.tmp")
tmp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+"\n")
tmp.replace(p)
print("FS1121_BACKUP="+backup.name)
print("FS1121_CONNECTION_COUNT="+str(len(connections)))
PY
docker restart "$CB" >/dev/null
ready=NO
for attempt in $(seq 1 60); do
  code="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ 2>/dev/null || true)"
  if [[ "$code" == 200 ]];then ready=YES;break;fi
  sleep 2
done
echo "FS1121_HTTP_READY=$ready"
[[ "$ready" == YES ]] || exit 1
echo "FS1121_DRIVER_WARNINGS_BEGIN"
docker logs --since 2m "$CB" 2>&1 | grep 'DataSourceSerializerModern - Can.t find driver' | tail -12 || true
echo "FS1121_DRIVER_WARNINGS_END"
echo "FS1121_RESULT=METADATA_PROVISIONED_CREDENTIALS_REQUIRED_FOR_SQL_LOGIN"
