#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
fail=0
command -v python3 >/dev/null || { echo FAIL|PYTHON_MISSING; exit 1; }
python3 - <<'PY'
import ast, pathlib, sys
root=pathlib.Path('app')
for p in root.rglob('*.py'):
    ast.parse(p.read_text(encoding='utf-8'), filename=str(p))
print('PASS|PYTHON_AST')
PY
bash -n deploy/*.sh tests/*.sh
python3 - <<'PY'
import json, pathlib
m=json.loads(pathlib.Path('manifests/MANIFEST.json').read_text())
assert m['release']=='V7.8'
assert m['runtime_qualification_required'] is True
print('PASS|MANIFEST')
PY
# Internal port exposure assertion from Compose source.
python3 - <<'PY'
import re
s=open('compose.yml',encoding='utf-8').read()
for p in ['810','811','812','813','814','815','816','817','818','819','7233','5432','3306']:
    if re.search(r'ports:\s*\[.*["\']'+p+r'(?::|["\'])',s):
        raise SystemExit(f'FAIL|FORBIDDEN_PUBLISHED_PORT|{p}')
print('PASS|PORT_POLICY')
PY
echo STATIC_GATE=PASS
