#!/usr/bin/env bash
set -euo pipefail
CB=aiops2-rebuild-cloudbeaver
VOL=aiops2-cloudbeaver-workspace
echo "FS1119_MODE=REMOVE_ONLY_UNVERIFIED_FS1115_DATASOURCE_ENTRIES"
docker inspect "$CB" --format '{{.State.Running}}' | grep -Fx true >/dev/null
docker run --rm -i --mount "type=volume,source=$VOL,target=/workspace" python:3.12-alpine python - <<'PY'
import json,pathlib,shutil,datetime
p=pathlib.Path("/workspace/GlobalConfiguration/.dbeaver/data-sources.json")
cfg=json.loads(p.read_text())
connections=cfg.get("connections",{})
expected={
 "aiops2-core":("aiops2-rebuild-postgres","5432"),
 "aiops2-temporal":("aiops2-rebuild-temporal-postgres","5432"),
 "aiops2-glpi":("aiops2-rebuild-glpi-db","3306"),
}
for key,(host,port) in expected.items():
 c=connections.get(key)
 if c is None:continue
 details=c.get("configuration") or {}
 if details.get("host")!=host or str(details.get("port"))!=port:
  raise SystemExit("FS1119_REFUSE_MODIFIED_CONNECTION="+key)
 if c.get("provider")!="generic":
  raise SystemExit("FS1119_REFUSE_MODIFIED_PROVIDER="+key)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
backup=p.with_name(p.name+".fs1119-"+stamp+".bak")
shutil.copy2(p,backup)
for key in expected:
 if key in connections:
  del connections[key]
  print("FS1119_REMOVED_UNVERIFIED="+key)
tmp=p.with_name(p.name+".fs1119.tmp")
tmp.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+"\n")
tmp.replace(p)
print("FS1119_BACKUP="+backup.name)
print("FS1119_REMAINING_CONNECTIONS="+str(len(connections)))
PY
docker restart "$CB" >/dev/null
ready=NO
for attempt in $(seq 1 60); do
  code="$(curl -sS --max-time 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8978/ 2>/dev/null || true)"
  if [[ "$code" == 200 ]];then ready=YES;break;fi
  sleep 2
done
echo "FS1119_HTTP_READY=$ready"
[[ "$ready" == YES ]] || exit 1
echo "FS1119_PORTAL_IMAGE=$(docker inspect aiops2-rebuild-portal --format '{{.Config.Image}}')"
echo "FS1119_RESULT=UNVERIFIED_ENTRIES_REMOVED"
echo "FS1119_NEXT=CREATE_CONNECTIONS_USING_CLOUDBEAVER_NATIVE_ADMIN_UI"
