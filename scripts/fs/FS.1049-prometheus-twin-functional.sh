#!/usr/bin/env bash
# FS.1049 — Functional read-only Prometheus and Twin data qualification.
set -euo pipefail
NAME=aiops2-rebuild-portal
echo "FS1049_MODE=READ_ONLY_FUNCTIONAL_DATA"
[[ "$(docker inspect "$NAME" --format '{{.Config.Image}}')" == "aiops2-portal:fs1040-sql-guard-candidate" ]] || { echo "FS1049_IMAGE=FAIL"; exit 2; }
docker exec -i "$NAME" python - <<'PY'
import json,urllib.request,urllib.error
BASE_PROM="http://aiops2-rebuild-prometheus:9090"
BASE_TWIN="http://aiops2-rebuild-twin:811"
checks=0;failures=0
def fetch(label,url):
 global checks,failures
 checks+=1
 try:
  req=urllib.request.Request(url,method="GET",headers={"Accept":"application/json"})
  with urllib.request.urlopen(req,timeout=8) as r:
   raw=r.read(2_000_001)
   if len(raw)>2_000_000:raise ValueError("payload_too_large")
   obj=json.loads(raw)
   print("FS1049_FETCH="+label+" HTTP="+str(r.status)+" JSON_TYPE="+type(obj).__name__)
   return obj
 except Exception as e:
  failures+=1
  print("FS1049_FETCH="+label+" ERROR="+type(e).__name__)
  return None
def check(label,passed,detail=""):
 global checks,failures
 checks+=1
 if not passed:failures+=1
 print("FS1049_CHECK="+label+" RESULT="+("PASS" if passed else "FAIL")+((" "+detail) if detail else ""))
targets=fetch("PROM_TARGETS",BASE_PROM+"/api/v1/targets?state=active")
if isinstance(targets,dict):
 active=((targets.get("data") or {}).get("activeTargets") or [])
 check("PROM_API_SUCCESS",targets.get("status")=="success")
 check("PROM_TARGETS_LIST",isinstance(active,list))
 if isinstance(active,list):
  health={}
  for t in active:
   k=str(t.get("health","unknown")).lower()
   health[k]=health.get(k,0)+1
  print("FS1049_PROM_TARGET_COUNT="+str(len(active)))
  for k,n in sorted(health.items()):
   print("FS1049_PROM_TARGET_HEALTH="+k+" COUNT="+str(n))
query=fetch("PROM_UP_QUERY",BASE_PROM+"/api/v1/query?query=up")
if isinstance(query,dict):
 data=query.get("data") or {}
 results=data.get("result") or []
 check("PROM_UP_QUERY_SUCCESS",query.get("status")=="success" and data.get("resultType")=="vector")
 check("PROM_UP_SERIES",isinstance(results,list), "COUNT="+str(len(results)) if isinstance(results,list) else "")
 if isinstance(results,list):
  up=down=other=0
  for item in results:
   try:
    value=float(item["value"][1])
    if value==1:up+=1
    elif value==0:down+=1
    else:other+=1
   except (KeyError,IndexError,TypeError,ValueError):other+=1
  print("FS1049_PROM_UP="+str(up)+" DOWN="+str(down)+" OTHER="+str(other))
graph=fetch("TWIN_GRAPH",BASE_TWIN+"/api/twin/graph")
if isinstance(graph,dict):
 print("FS1049_TWIN_TOP_LEVEL_KEYS="+",".join(sorted(str(k) for k in graph.keys())[:30]))
 for key in ("nodes","edges","links","vertices","relationships"):
  value=graph.get(key)
  if isinstance(value,list):
   print("FS1049_TWIN_COLLECTION="+key+" COUNT="+str(len(value)))
 check("TWIN_GRAPH_OBJECT",True)
else:
 check("TWIN_GRAPH_OBJECT",False)
print("FS1049_CHECKS="+str(checks)+" FAILURES="+str(failures))
print("FS1049_RESULT="+("PASS" if failures==0 else "FAIL"))
raise SystemExit(0 if failures==0 else 1)
PY
