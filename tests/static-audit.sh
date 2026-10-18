#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import pathlib,ast
for p in pathlib.Path('app').rglob('*.py'): ast.parse(p.read_text(),filename=str(p))
PY
for f in app/*/Dockerfile; do test -f "$f" || { echo "FAIL|dockerfile|$f"; exit 1; }; done
grep -q '7777:777' compose.yml
grep -q '8080:80' compose.yml
grep -q '5678:5678' compose.yml
grep -q '9090:9090' compose.yml
grep -q '3000:3000' compose.yml
grep -q 'aiops2-execution:' compose.yml
grep -q 'aiops2-temporal-data:' compose.yml
grep -q 'internal: true' compose.yml
grep -q 'AIOPS_INTERNAL_TOKEN' config/.env.example
echo STATIC_AUDIT=PASS
