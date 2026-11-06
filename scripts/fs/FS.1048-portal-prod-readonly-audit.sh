#!/usr/bin/env bash
# FS.1048 — production portal post-deployment read-only verification.
set -euo pipefail
NAME=aiops2-rebuild-portal
EXPECTED=aiops2-portal:fs1040-sql-guard-candidate
BASE=http://127.0.0.1:7777
echo "FS1048_MODE=READ_ONLY_POST_DEPLOY"
docker inspect "$NAME" | python3 -c '
import json,sys
d=json.load(sys.stdin)[0]
c=d["Config"]; n=d["NetworkSettings"]["Networks"]; m=d.get("Mounts") or []
print("FS1048_CONTAINER_STATE="+str(d["State"]["Status"]))
print("FS1048_IMAGE="+str(c["Image"]))
print("FS1048_NETWORKS="+",".join(sorted(n)))
print("FS1048_MOUNT_DESTINATIONS="+",".join(sorted(x["Destination"] for x in m)))
assert d["State"]["Running"]
assert c["Image"]=="aiops2-portal:fs1040-sql-guard-candidate"
assert set(n)=={"aiops2-rebuild-control","aiops2-rebuild-integration","aiops2-rebuild-public"}
assert {x["Destination"] for x in m}=={"/data/fs-demo","/var/lib/aiops-fs-demo"}
print("FS1048_CONTAINER_PARITY=PASS")
'
for path in /health /explorer/databases /explorer/prometheus /explorer/cmdb /api/explorer/catalog; do
  status="$(curl --noproxy '*' -sS --max-time 6 -o /dev/null -w '%{http_code}' "$BASE$path" || true)"
  echo "FS1048_HTTP=$path STATUS=$status"
  if [[ "$status" != 200 ]]; then echo "FS1048_HTTP=FAIL"; exit 1; fi
done
echo "FS1048_HTTP=PASS"
# Catalog is returned by the portal itself; show only booleans and connector IDs.
curl --noproxy '*' -fsS --max-time 8 "$BASE/api/explorer/catalog" | python3 -c '
import json,sys
d=json.load(sys.stdin)
print("FS1048_CATALOG_JSON=PASS")
def walk(v,p="",depth=0):
 if depth>4:return
 if isinstance(v,dict):
  for k,x in v.items():
   if k in ("configured","enabled","read_only","read-only") and isinstance(x,bool):
    print("FS1048_CATALOG_FLAG="+p+"."+k+"="+str(x).lower())
   elif k in ("services",) and isinstance(x,dict):
    for name,flag in sorted(x.items()):
     if isinstance(flag,bool):print("FS1048_SERVICE="+str(name)+" CONFIGURED="+str(flag).lower())
   elif k in ("database_sources","sources","databases") and isinstance(x,list):
    for item in x:
     if isinstance(item,dict) and isinstance(item.get("id"),str):
      print("FS1048_DATABASE="+item["id"]+" CONFIGURED="+str(item.get("configured","unknown")).lower())
   elif isinstance(x,(dict,list)):walk(x,p+"."+k,depth+1)
 elif isinstance(v,list):
  for x in v:walk(x,p,depth+1)
walk(d)
'
# Test upstream Prometheus and Twin reachability FROM the portal network.
# HTTP GET only. Never print payloads or auth tokens.
docker exec -i "$NAME" python - <<'PY'
import urllib.request
checks={
 "PROMETHEUS_READY":"http://aiops2-rebuild-prometheus:9090/-/ready",
 "PROMETHEUS_TARGETS":"http://aiops2-rebuild-prometheus:9090/api/v1/targets?state=active",
 "TWIN_HEALTH":"http://aiops2-rebuild-twin:811/health",
 "TWIN_GRAPH":"http://aiops2-rebuild-twin:811/api/twin/graph",
 "CORE_HEALTH":"http://aiops2-rebuild-core:810/health",
}
for name,url in checks.items():
 try:
  with urllib.request.urlopen(urllib.request.Request(url,method="GET"),timeout=5) as r:
   print("FS1048_UPSTREAM="+name+" STATUS="+str(r.status))
 except Exception as exc:
  print("FS1048_UPSTREAM="+name+" ERROR="+type(exc).__name__)
PY
echo "FS1048_DATABASE_POLICY=NO_DB_CONNECTIONS_NO_SQL"
echo "FS1048_CMDB_POLICY=NO_GLPI_SESSION_OR_MUTATION"
echo "FS1048_AUDIT=COMPLETE"
