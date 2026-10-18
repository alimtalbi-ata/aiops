#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
# Historical identifiers are permitted only in explicit retirement/documentation material.
if grep -RIn --exclude='retire-legacy.sh' --exclude='static-audit.sh' --exclude='LEGACY-RETIREMENT.md' \
  -E 'aiops_v1|aiops-temporal-(integration|fastpath)|v28\.|v145|fastpath|candidate|rollback_' compose.yml app config deploy 2>/tmp/name-audit.err | grep -v 'retirement-plan.sh'; then
  echo 'FAIL|legacy-runtime-name-found'; exit 1
fi
python3 - <<'PY'
import pathlib,ast
for p in pathlib.Path('app').rglob('*.py'): ast.parse(p.read_text(),filename=str(p))
PY
grep -q '"7777:777"' compose.yml
grep -q '"8080:80"' compose.yml
grep -q 'aiops-execution:' compose.yml
grep -q 'aiops-temporal-data:' compose.yml
grep -q 'internal: true' compose.yml
grep -q 'AIOPS_INTERNAL_TOKEN' config/.env.example
grep -q '7777:777' compose.yml
grep -q '8080:80' compose.yml
grep -q '5678:5678' compose.yml
grep -q '9090:9090' compose.yml
grep -q '3000:3000' compose.yml
! grep -q 'ports:.*777:7777' compose.yml
echo STATIC_AUDIT=PASS
