#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${1:-.env}"
if [[ -f "$ENV_FILE" ]]; then
  chmod 600 "$ENV_FILE"
  echo 'ENV_EXISTS=UNCHANGED'
  exit 0
fi
command -v openssl >/dev/null 2>&1 || { echo 'FAIL|openssl_missing_for_secret_generation'; exit 1; }
cp config/.env.example "$ENV_FILE"
chmod 600 "$ENV_FILE"
set_value() {
  local key="$1" value="$2"
  if ! grep -q "^${key}=" "$ENV_FILE"; then
    echo "FAIL|missing_template_key|${key}" >&2
    exit 1
  fi
  sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
}
# Core, worker and simulator share this internal authentication token by contract.
INTERNAL_TOKEN="$(openssl rand -hex 32)"
set_value AIOPS_ADMIN_TOKEN "$INTERNAL_TOKEN"
set_value AIOPS_INTERNAL_TOKEN "$INTERNAL_TOKEN"
set_value AIOPS_PORTAL_READ_TOKEN "$(openssl rand -hex 32)"
set_value AIOPS_PORTAL_OPERATOR_TOKEN "$(openssl rand -hex 32)"
set_value POSTGRES_PASSWORD "$(openssl rand -hex 32)"
set_value GLPI_DB_PASSWORD "$(openssl rand -hex 32)"
set_value GLPI_DB_ROOT_PASSWORD "$(openssl rand -hex 32)"
set_value GRAFANA_ADMIN_PASSWORD "$(openssl rand -hex 32)"
set_value N8N_ENCRYPTION_KEY "$(openssl rand -hex 32)"
echo 'ENV_CREATED=1'
echo 'SECRETS_GENERATED=1'
echo 'SECRETS_PRINTED=0'
