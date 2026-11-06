#!/usr/bin/env bash
set -euo pipefail
echo "FS1065_MODE=READ_ONLY_VISUAL_DATA_CONTRACT"
python3 - <<'PY'
import json,urllib.request
base="http://127.0.0.1:7777"
def get(path):
 with urllib.request.urlopen(base+path,timeout=12) as r:
  assert r.status==200,(path,r.status)
  return r.read(2500000)
html=get("/explorer/visual").decode("utf-8")
for marker in ('id="graph"','id="targets"','id="search"','id="refresh"',
               '/api/fs1051/prometheus','/api/fs1051/twin',
               'addEventListener("click"','addEventListener("input"'):
 assert marker in html,"missing UI marker: "+marker
print("FS1065_UI_STRUCTURE=PASS",flush=True)
p=json.loads(get("/api/fs1051/prometheus"))
assert all(isinstance(p.get(k),int) and p[k]>=0 for k in ("up","down","total"))
assert isinstance(p.get("targets"),list)
assert p["up"]+p["down"]<=p["total"],"target totals inconsistent"
for t in p["targets"]:
 assert isinstance(t,dict)
 assert all(isinstance(t.get(k),str) for k in ("job","instance","health"))
print("FS1065_PROMETHEUS_UP="+str(p["up"])+" DOWN="+str(p["down"])+" TOTAL="+str(p["total"])+" TARGET_ROWS="+str(len(p["targets"])),flush=True)
t=json.loads(get("/api/fs1051/twin"))
assert isinstance(t.get("nodes"),list) and isinstance(t.get("edges"),list)
assert isinstance(t.get("total_nodes"),int) and isinstance(t.get("total_edges"),int)
assert t["total_nodes"]>=len(t["nodes"]) and t["total_edges"]>=len(t["edges"])
assert all(isinstance(n,dict) for n in t["nodes"])
assert all(isinstance(e,dict) for e in t["edges"])
print("FS1065_TWIN_NODES="+str(t["total_nodes"])+" EDGES="+str(t["total_edges"]),flush=True)
print("FS1065_DATA_CONTRACT=PASS",flush=True)
print("FS1065_BROWSER_RENDERING=NOT_TESTED",flush=True)
print("FS1065_RESULT=PASS",flush=True)
PY
