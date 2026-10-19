#!/usr/bin/env bash
# Repeatable source/CI-like qualification loop for an isolated AIOps 2.0 target.
# No containers are changed unless APPLY_RUNTIME=1 is explicitly set.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "===== AIOps 2.0 qualification loop ====="
echo "ROOT=$ROOT"
echo "BRANCH=$(git branch --show-current 2>/dev/null || echo detached)"
echo "COMMIT=$(git rev-parse HEAD 2>/dev/null || echo unknown)"

[[ -f .env ]] || { echo 'FAIL|env_file_missing|run deploy/init-env.sh for a new isolated install'; exit 1; }
bash deploy/check-secrets.sh .env
bash -n deploy/install.sh deploy/preflight.sh deploy/init-env.sh deploy/check-secrets.sh \
  tests/qualification.sh tests/synthetic-e2e.sh tests/static-audit.sh deploy/qualify-update.sh
python3 -m compileall -q app tests
python3 -m unittest discover -s tests -p 'test_policy_safety.py' -v
PYTHONPATH=app python3 -m unittest discover -s tests -p 'test_portal_auth.py' -v
PYTHONPATH=app python3 -m unittest discover -s tests -p 'test_shared_http.py' -v
PYTHONPATH=app python3 -m unittest discover -s tests -p 'test_idempotency_receipts.py' -v
bash tests/test_preflight_secrets.sh
bash tests/static-audit.sh
docker compose --env-file .env config >/dev/null
echo 'SOURCE_AND_CONFIG_QUALIFICATION=PASS'

if [[ "${APPLY_RUNTIME:-0}" != "1" ]]; then
  echo 'RUNTIME_APPLY=SKIPPED|set APPLY_RUNTIME=1 only on an approved isolated qualification target'
  exit 0
fi

[[ "${ISOLATED_TARGET:-}" == "1" ]] || { echo 'FAIL|isolated_target_confirmation_required|set ISOLATED_TARGET=1'; exit 1; }
[[ "${BACKUP_CONFIRMED:-}" == "1" ]] || { echo 'FAIL|backup_confirmation_required|backup database and persistent volumes before runtime update'; exit 1; }
[[ "${CONFIRM_RUNTIME_UPDATE:-}" == "I_APPROVE_AIOPS2_QUALIFICATION_UPDATE" ]] || {
  echo 'FAIL|runtime_confirmation_required|set CONFIRM_RUNTIME_UPDATE=I_APPROVE_AIOPS2_QUALIFICATION_UPDATE'
  exit 1
}

echo '===== BUILD ====='
docker compose --env-file .env build --pull
echo '===== APPLY ====='
docker compose --env-file .env up -d
echo '===== RUNTIME QUALIFICATION ====='
bash tests/qualification.sh
bash tests/synthetic-e2e.sh
echo 'RUNTIME_QUALIFICATION=PASS'
