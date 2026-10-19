#!/usr/bin/env bash
# Add the dedicated Portal operator secret to an existing local .env without
# rotating or printing any other credential. Run deliberately during upgrade.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${1:-.env}"
[[ -f "$ENV_FILE" ]] || { echo "FAIL|env_file_missing|$ENV_FILE"; exit 1; }
command -v openssl >/dev/null 2>&1 || { echo 'FAIL|openssl_missing'; exit 1; }
chmod 600 "$ENV_FILE"
CURRENT="$(sed -n 's/^AIOPS_PORTAL_OPERATOR_TOKEN=//p' "$ENV_FILE" | tail -n 1)"
if [[ -n "$CURRENT" && "$CURRENT" != "CHANGE_ME" && "$CURRENT" != "REPLACE_ME" && "$CURRENT" != "GENERATE_ME" ]]; then
  echo 'PORTAL_OPERATOR_TOKEN=EXISTING_UNCHANGED'
  exit 0
fi
TOKEN="$(openssl rand -hex 32)"
if grep -q '^AIOPS_PORTAL_OPERATOR_TOKEN=' "$ENV_FILE"; then
  sed -i "s|^AIOPS_PORTAL_OPERATOR_TOKEN=.*|AIOPS_PORTAL_OPERATOR_TOKEN=$TOKEN|" "$ENV_FILE"
else
  printf '\nAIOPS_PORTAL_OPERATOR_TOKEN=%s\n' "$TOKEN" >>"$ENV_FILE"
fi
unset TOKEN CURRENT
chmod 600 "$ENV_FILE"
echo 'PORTAL_OPERATOR_TOKEN=GENERATED|value_not_printed'
