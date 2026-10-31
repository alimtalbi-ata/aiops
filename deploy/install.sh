#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Create unique secrets only on a fresh installation; existing .env is preserved.
bash deploy/init-env.sh
bash deploy/check-secrets.sh .env
bash deploy/preflight.sh

# Legacy retirement is deliberately separate and explicit.
if [[ "${RETIRE_LEGACY:-0}" == "1" ]]; then
  bash deploy/retire-legacy.sh
fi

docker compose --env-file .env config --quiet
docker compose --env-file .env build --pull

# Start PostgreSQL first. The entrypoint applies baseline migrations 000-008.
docker compose --env-file .env up -d --wait aiops2-postgres

# Apply 009+ through the checksum-journaled transactional migration runner.
bash deploy/migrate.sh

# Start the full stack only after the schema upgrade is recorded.
docker compose --env-file .env up -d --wait
bash tests/qualification.sh

if grep -qx 'AIOPS_DEMO_PROVIDER_KIND=REAL' .env; then
  bash tests/synthetic-e2e.sh
else
  echo 'SYNTHETIC_E2E=SKIP|real_model_provider_not_configured'
fi
