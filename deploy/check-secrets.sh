#!/usr/bin/env bash
set -Eeuo pipefail
ENV_FILE="${1:-.env}"
[[ -f "$ENV_FILE" ]] || { echo 'FAIL|env_file_missing'; exit 1; }
env_value() {
  local key="$1"
  awk -F= -v key="$key" '$1 == key { sub(/^[^=]*=/, ""); value=$0 } END { print value }' "$ENV_FILE"
}
MODE="$(env_value AIOPS_DEMO_MODE)"
MODE="${MODE:-0}"
if [[ "$MODE" == "1" ]]; then
  echo 'WARN|DEMO_MODE_ENABLED|use only on an isolated local demo; never in production'
  exit 0
fi
if [[ "$MODE" != "0" ]]; then
  echo 'FAIL|invalid_AIOPS_DEMO_MODE|expected_0_or_1'
  exit 1
fi
failures=0
check_secret() {
  local key="$1" default="$2" value
  value="$(env_value "$key")"
  if [[ -z "$value" || "$value" == "$default" || "$value" == "CHANGE_ME" || "$value" == "REPLACE_ME" || "$value" == "GENERATE_ME" ]]; then
    echo "FAIL|unsafe_or_missing_secret|$key"
    failures=1
  fi
}
check_secret POSTGRES_PASSWORD 'Newaiops26$'
check_secret AIOPS_ADMIN_TOKEN 'Newaiops26$'
check_secret AIOPS_INTERNAL_TOKEN 'Newaiops26$'
check_secret GLPI_DB_PASSWORD 'Newaiops26$'
check_secret GLPI_DB_ROOT_PASSWORD 'Newaiops26$'
check_secret GRAFANA_ADMIN_PASSWORD 'Newaiops26$'
check_secret N8N_ENCRYPTION_KEY 'Newaiops26$-N8N'
if [[ "$failures" -ne 0 ]]; then
  echo 'ACTION|run deploy/init-env.sh only for a new installation, or replace every listed value in .env; existing .env files are never rotated automatically'
  exit 1
fi
if [[ "$(env_value AIOPS_ADMIN_TOKEN)" != "$(env_value AIOPS_INTERNAL_TOKEN)" ]]; then
  echo 'FAIL|internal_token_mismatch|AIOPS_ADMIN_TOKEN_and_AIOPS_INTERNAL_TOKEN_must_match'
  exit 1
fi
echo 'SECRET_PREFLIGHT=PASS'
