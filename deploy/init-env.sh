#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  chmod 600 .env
  migrated=0
  # Repair only known broken defaults from previous repository-generated templates.
  if grep -Fxq 'TEMPORAL_IMAGE=temporalio/auto-setup:1.32.1' .env; then
    sed -i 's|^TEMPORAL_IMAGE=temporalio/auto-setup:1.32.1$|TEMPORAL_IMAGE=temporalio/server:1.31.0|' .env
    migrated=1
  fi
  if grep -Fxq 'TEMPORAL_UI_IMAGE=temporalio/ui:2.56.0' .env; then
    sed -i 's|^TEMPORAL_UI_IMAGE=temporalio/ui:2.56.0$|TEMPORAL_UI_IMAGE=temporalio/ui:2.49.1|' .env
    migrated=1
  fi
  # Add new non-secret defaults without overwriting any operator-configured values.
  while IFS= read -r line; do
    case "$line" in
      *=*)
        key="${line%%=*}"
        if ! grep -q "^\${key}=" .env; then
          printf '%s\n' "$line" >> .env
          migrated=1
        fi
        ;;
    esac
  done < config/.env.example
  chmod 600 .env
  if [[ "$migrated" == 1 ]]; then echo 'ENV_EXISTING_UPDATED=1'; else echo 'ENV_EXISTS=UNCHANGED'; fi
  exit 0
fi
command -v openssl >/dev/null 2>&1 || { echo 'FAIL|openssl_missing_for_secret_generation'; exit 1; }
cp config/.env.example .env
chmod 600 .env
set_value() {
  local key="$1" value="$2"
  if ! grep -q "^${key}=" .env; then
    echo "FAIL|missing_template_key|${key}" >&2
    exit 1
  fi
  sed -i "s|^${key}=.*|${key}=${value}|" .env
}
# Core, worker and simulator share this internal authentication token by contract.
INTERNAL_TOKEN="$(openssl rand -hex 32)"
set_value AIOPS_ADMIN_TOKEN "$INTERNAL_TOKEN"
set_value AIOPS_INTERNAL_TOKEN "$INTERNAL_TOKEN"
set_value POSTGRES_PASSWORD "$(openssl rand -hex 32)"
set_value GLPI_DB_PASSWORD "$(openssl rand -hex 32)"
set_value GLPI_DB_ROOT_PASSWORD "$(openssl rand -hex 32)"
set_value GRAFANA_ADMIN_PASSWORD "$(openssl rand -hex 32)"
set_value N8N_ENCRYPTION_KEY "$(openssl rand -hex 32)"
echo 'ENV_CREATED=1'
echo 'SECRETS_GENERATED=1'
echo 'SECRETS_PRINTED=0'
