#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import ast,pathlib
for p in pathlib.Path('app').rglob('*.py'):ast.parse(p.read_text(),filename=str(p))
for name in ('core','twin','evidence','policy','copilot','worker','simulator','portal','intelligence','rag','integration'):
 for file in ('Dockerfile','main.py'):
  if not (pathlib.Path('app')/name/file).is_file():raise SystemExit('FAIL|MISSING|'+name+'/'+file)
PY
echo STATIC_AUDIT=PASS
