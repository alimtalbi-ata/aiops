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
grep -q 'deploy/check-secrets.sh' deploy/preflight.sh
grep -q 'RUN_ID_2' tests/synthetic-e2e.sh
grep -q 'RESOLVED' tests/synthetic-e2e.sh
grep -q 'E2E_ASSERTIONS=PASS' tests/synthetic-e2e.sh
grep -q 'maximum_interval=datetime.timedelta' app/worker/main.py
! grep -q 'max_interval=datetime.timedelta' app/worker/main.py
grep -A20 '^  aiops2-n8n:' compose.yml | grep -q 'aiops2-data'
grep -Fq '$N8N_DATABASE' compose.yml
grep -Fq '$PGHOST' compose.yml
grep -q 'APP_HEALTH_TIMEOUT' tests/qualification.sh
if grep -RIn 'Newaiops26' app compose.yml; then echo 'FAIL|hardcoded_runtime_secret'; exit 1; fi
grep -Fq '${POSTGRES_PASSWORD:?POSTGRES_PASSWORD_required}' compose.yml
grep -Fq '${AIOPS_INTERNAL_TOKEN:?AIOPS_INTERNAL_TOKEN_required}' compose.yml
echo STATIC_AUDIT=PASS
