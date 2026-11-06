#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.964 | HTTP HELPER AND GUARD AUDIT ====='
docker exec -i aiops2-rebuild-worker python - <<'PY'
import ast, inspect
from pathlib import Path
import shared.http as h
p=Path('/app/worker/main.py')
s=p.read_text()
tree=ast.parse(s)
print('===== GET_JSON IMPLEMENTATION =====')
try:
 print(inspect.getsource(h.get_json))
except (OSError,TypeError) as exc:
 print('SOURCE_UNAVAILABLE',type(exc).__name__)
print('===== GUARD IMPLEMENTATION =====')
for n in tree.body:
 if isinstance(n,ast.AsyncFunctionDef) and n.name=='start':
  print(ast.get_source_segment(s,n)[:3500])
  break
print('===== HTTP 404 EXCEPTION CLASS =====')
try:
 h.get_json('http://aiops2-core:810','/api/runs/RUN-FS964-DOES-NOT-EXIST',timeout=4,retries=0)
except Exception as exc:
 print('EXCEPTION_TYPE=',type(exc).__module__+'.'+type(exc).__name__)
 print('HTTP_STATUS=',getattr(getattr(exc,'response',None),'status_code','UNKNOWN'))
else:
 print('UNEXPECTED_NO_EXCEPTION')
print('REQUEST_METHOD=GET_ONLY')
print('WORKFLOWS_STARTED=NO')
PY
echo '===== END FS.964 ====='
