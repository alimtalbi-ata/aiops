#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.963 | CORE READ-ONLY DIAGNOSTIC ====='
docker exec -i aiops2-rebuild-worker python - <<'PY'
import ast, os, requests
from pathlib import Path
src=Path('/app/worker/main.py').read_text()
tree=ast.parse(src)
for n in tree.body:
    if isinstance(n,(ast.Import,ast.ImportFrom)):
        s=ast.get_source_segment(src,n) or ''
        if 'get_json' in s: print('GET_JSON_IMPORT='+s)
core=os.getenv('CORE_URL','http://aiops2-core:810')
print('CORE_URL_EFFECTIVE='+core)
for path in ('/health','/api/runs/RUN-FS961-DOES-NOT-EXIST','/api/runs/RUN-8FD05627DCB0DE1A'):
    try:
        r=requests.get(core.rstrip('/')+path,timeout=8,allow_redirects=False)
        print('GET',path,'HTTP',r.status_code,'CONTENT_TYPE',r.headers.get('content-type',''))
        if r.status_code==200 and path.startswith('/api/runs/'):
            body=r.json()
            print('RUN_STATUS=',body.get('run',{}).get('status') if isinstance(body,dict) else 'unexpected-response')
    except Exception as exc:
        print('GET',path,'ERROR_TYPE',type(exc).__name__)
print('NETWORK_METHOD=GET_ONLY')
print('WORKFLOWS_STARTED=NO')
PY
echo '===== END FS.963 ====='
