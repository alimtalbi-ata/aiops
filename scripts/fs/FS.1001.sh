#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1001 | PORTAL / METRICS / CMDB CONTRACT DIAGNOSTICS ====='
echo 'READ_ONLY=YES'
echo '===== PORTAL SOURCE ROUTES ====='
python3 - <<'PY'
import ast,pathlib
for root in ['/home/aiops/aiops2-v2-delivery','/home/aiops/aiops2-fs-demo-source']:
 p=pathlib.Path(root)/'app/portal/main.py'
 if not p.exists():continue
 try:t=ast.parse(p.read_text())
 except Exception as e:print('PORTAL_PARSE_ERROR='+type(e).__name__);continue
 routes=[]
 for node in ast.walk(t):
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
   for dec in node.decorator_list:
    if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.args and isinstance(dec.args[0],ast.Constant) and isinstance(dec.args[0].value,str):
     if dec.func.attr in ('get','post','api_route'):routes.append((dec.func.attr,dec.args[0].value,node.name))
 print('PORTAL_SOURCE='+str(p))
 for method,path,name in sorted(set(routes)):print('ROUTE='+method+' '+path+' HANDLER='+name)
PY
echo '===== PROMETHEUS TARGETS AND ALERTS (READ ONLY) ====='
docker exec aiops2-rebuild-prometheus sh -c 'wget -q -T 4 -O - http://127.0.0.1:9090/api/v1/targets?state=active' | python3 -c 'import json,sys; d=json.load(sys.stdin); a=d.get("data",{}).get("activeTargets",[]); print("ACTIVE_TARGETS="+str(len(a))); [print("TARGET="+str(x.get("labels",{}).get("job"))+" HEALTH="+str(x.get("health"))+" ERROR="+str(x.get("lastError",""))[:160]) for x in a[:35]]' || echo 'PROMETHEUS_TARGET_QUERY=UNAVAILABLE'
docker exec aiops2-rebuild-prometheus sh -c 'wget -q -T 4 -O - http://127.0.0.1:9090/api/v1/alerts' | python3 -c 'import json,sys; d=json.load(sys.stdin); a=d.get("data",{}).get("alerts",[]); print("PROMETHEUS_ALERTS="+str(len(a))); [print("ALERT="+str(x.get("labels",{}).get("alertname"))+" STATE="+str(x.get("state"))) for x in a[:20]]' || echo 'PROMETHEUS_ALERT_QUERY=UNAVAILABLE'
echo '===== METRICS CONTENT-TYPE / BODY SAMPLE (E2E) ====='
docker exec -i aiops2-e2e-v1-aiops2-core-1 python - <<'PY'
import urllib.request,urllib.error
for host in ('http://127.0.0.1:810','http://aiops2-policy:813','http://aiops2-twin:811','http://aiops2-evidence:812','http://aiops2-intelligence:817'):
 try:
  with urllib.request.urlopen(host+'/metrics',timeout=3) as r:
   b=r.read(320).decode('utf-8','replace').replace('\n',' ')
   print('METRICS='+host+' STATUS='+str(r.status)+' CONTENT_TYPE='+r.headers.get('Content-Type','')+' SAMPLE='+repr(b))
 except Exception as e:print('METRICS='+host+' ERROR='+type(e).__name__+' '+str(e)[:100])
PY
echo '===== CMDB AND DATABASE READ-ONLY SOURCE DISCOVERY ====='
for f in /home/aiops/aiops2-v2-delivery/db/migrations/001_schema.sql /home/aiops/aiops2-v2-delivery/docs/DATABASE-SCHEMA-CATALOG.md; do
 if [[ -r "$f" ]]; then
  echo "FILE=$f"
  grep -Ei 'CREATE TABLE|^##|^###' "$f" | head -55 || true
 fi
done
echo '===== PORTAL CURRENT HEALTH (NO AUTH TOKEN OUTPUT) ====='
docker exec aiops2-rebuild-portal python -c 'import urllib.request; u="http://127.0.0.1:777/health"; r=urllib.request.urlopen(u,timeout=5); print("PORTAL_HEALTH_HTTP="+str(r.status)+" BODY="+repr(r.read(200).decode("utf-8","replace")))' || echo 'PORTAL_HEALTH=UNAVAILABLE'
echo 'WORKFLOWS_STARTED=0'
echo 'HTTP_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1001 ====='
