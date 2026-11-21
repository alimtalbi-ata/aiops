#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
grep -Fq 'temporalio/server:1.31.0' config/.env.example
grep -Fq 'temporalio/admin-tools:1.31.0' config/.env.example
grep -Fq 'TEMPORAL_UI_IMAGE=temporalio/ui:2.49.1' config/.env.example
grep -Fq 'temporalio/server:1.31.0' compose.yml
grep -Fq 'temporalio/admin-tools:1.31.0' compose.yml
grep -Fq 'service_completed_successfully' compose.yml
grep -Fq 'setup-schema -v 0.0' deploy/temporal/setup-postgres.sh
grep -Fq 'update-schema -d' deploy/temporal/setup-postgres.sh
grep -Fq 'already exists' deploy/temporal/setup-postgres.sh
grep -Fq 'namespace describe' deploy/temporal/create-namespace.sh
grep -Fq 'namespace create' deploy/temporal/create-namespace.sh
if grep -Fq 'temporalio/auto-setup' compose.yml config/.env.example; then
  echo 'FAIL|deprecated_temporal_auto_setup_image'
  exit 1
fi
bash -n deploy/temporal/setup-postgres.sh deploy/temporal/create-namespace.sh deploy/wait-stack.sh
echo TEMPORAL_CONTRACT=PASS
