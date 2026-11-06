#!/usr/bin/env bash
set -euo pipefail
echo '===== FS.975 | CANDIDATE PATCH COMPATIBILITY ====='
F=/home/aiops/aiops2-fs-demo-source/integration/worker-fs-candidate/main.py
EXPECTED=e9be751d2c8596fef78c5cea52d74c5b9182b54f0011cd72c68f61b436387dbd
echo "$EXPECTED  $F" | sha256sum -c -
python3 - "$F" <<'PY'
import ast,sys
p=sys.argv[1];s=open(p).read();t=ast.parse(s)
for token in ('from shared.http import','CORE=','ADMIN=','import os','import asyncio','from fastapi import'):
 print('IMPORT_OR_CONFIG_'+token.replace(' ','_').upper()+'='+str(token in s))
f=[n for n in t.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='start']
assert len(f)==1,'expected one async start'
src=ast.get_source_segment(s,f[0])
print('START_LINE='+str(f[0].lineno))
print('START_SOURCE_BEGIN')
print(src[:5500])
print('START_SOURCE_END')
print('GET_JSON_IMPORT='+str('get_json' in s))
print('REQUESTS_HTTPERROR_IMPORT='+str('requests.exceptions' in s))
print('PYTHON_AST=PASS')
PY
echo '===== SOURCE CONTROL ====='
git -C /home/aiops/aiops2-fs-demo-source status --short -- integration/worker-fs-candidate/main.py 2>/dev/null || true
echo 'FILES_MODIFIED=NO'
echo '===== END FS.975 ====='
