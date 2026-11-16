#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
import pathlib,ast
for p in pathlib.Path('app').rglob('*.py'): ast.parse(p.read_text(),filename=str(p))
PY
for f in app/*/Dockerfile; do test -f "$f" || { echo "FAIL|dockerfile|$f"; exit 1; }; done
grep -Fq 'AIOPS_PORTAL_HOST_PORT' compose.yml
grep -Fq 'AIOPS_GLPI_HOST_PORT' compose.yml
grep -Fq 'AIOPS_N8N_HOST_PORT' compose.yml
grep -Fq 'AIOPS_PROMETHEUS_HOST_PORT' compose.yml
grep -Fq 'AIOPS_GRAFANA_HOST_PORT' compose.yml
grep -q 'aiops2-execution:' compose.yml
grep -q 'aiops2-temporal-data:' compose.yml
grep -q 'internal: true' compose.yml
grep -Fq 'AIOPS_STACK_ID' compose.yml
grep -Fq 'AIOPS_BIND_IP' compose.yml
grep -q 'AIOPS_INTERNAL_TOKEN' config/.env.example
grep -q 'deploy/check-secrets.sh' deploy/preflight.sh
if grep -RIn 'Newaiops26' app compose.yml; then echo 'FAIL|hardcoded_runtime_secret'; exit 1; fi
grep -Fq '${POSTGRES_PASSWORD:?POSTGRES_PASSWORD_required}' compose.yml
grep -Fq '${AIOPS_INTERNAL_TOKEN:?AIOPS_INTERNAL_TOKEN_required}' compose.yml
if grep -Fq 'Newaiops26' 00-Deployment/install.sh; then echo 'FAIL|installer_embeds_password'; exit 1; fi
grep -Fq 'deploy/install-isolated.sh' 00-Deployment/install.sh
if grep -Fq 'RETIRE_LEGACY:-1' deploy/big-bang.sh; then echo 'FAIL|destructive_default_retirement'; exit 1; fi
echo STATIC_AUDIT=PASS
