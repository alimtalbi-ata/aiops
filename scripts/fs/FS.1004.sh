#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.1004 | TWIN 503 DATABASE / RUNTIME ISOLATION ====='
echo 'READ_ONLY=YES'
echo '===== TWIN INTERNAL ENDPOINTS ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
import urllib.request,urllib.error
for path in ('/health','/api/twin/summary','/metrics'):
 try:
  with urllib.request.urlopen('http://127.0.0.1:811'+path,timeout=5) as r:
   print('LOCAL='+path+' HTTP='+str(r.status)+' TYPE='+str(r.headers.get('Content-Type'))+' BODY='+repr(r.read(240).decode('utf-8','replace')))
 except urllib.error.HTTPError as e:print('LOCAL='+path+' HTTP='+str(e.code)+' BODY='+repr(e.read(300).decode('utf-8','replace')))
 except Exception as e:print('LOCAL='+path+' ERROR='+type(e).__name__+' '+str(e)[:130])
PY
echo '===== TWIN DATABASE READ-ONLY CONTRACT ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
try:
 from shared.db import db
 with db() as c:
  for name,sql in [('COUNT','select count(*) from aiops.twin_nodes'),('STATE','select count(*),count(*) filter(where state=\'DEGRADED\'),count(*) filter(where state=\'FAILED\') from aiops.twin_nodes')]:
   try:print('DB_'+name+'='+repr(c.execute(sql).fetchone()))
   except Exception as e:print('DB_'+name+'_ERROR='+type(e).__name__+' '+str(e)[:240])
except Exception as e:print('DB_CONNECT_ERROR='+type(e).__name__+' '+str(e)[:240])
PY
echo '===== ACTIVE RUNTIME METRICS SOURCE ====='
docker exec -i aiops2-rebuild-twin python - <<'PY'
import ast,pathlib
p=pathlib.Path('/app/twin/main.py')
if not p.exists():
 print('RUNTIME_SOURCE=NOT_FOUND')
else:
 t=ast.parse(p.read_text())
 for n in t.body:
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name=='metrics':
   print('RUNTIME_METRICS_LINES='+str(n.lineno)+'-'+str(n.end_lineno))
   print('RUNTIME_METRICS_SOURCE='+ast.unparse(n)[:1100])
PY
echo '===== DATABASE CONTAINER HEALTH ====='
docker inspect aiops2-rebuild-postgres --format 'DB_RUNNING={{.State.Running}} DB_RESTARTS={{.RestartCount}} DB_HEALTH={{if .State.Health}}{{.State.Health.Status}}{{else}}unknown{{end}}'
echo 'HTTP_WRITES=0'
echo 'PRODUCTION_RESTARTED=NO'
echo '===== END FS.1004 ====='
