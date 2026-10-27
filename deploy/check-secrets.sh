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
if [[ "$MODE" != "0" && "$MODE" != "1" ]]; then
  echo 'FAIL|invalid_AIOPS_DEMO_MODE|expected_0_or_1'
  exit 1
fi

if [[ "$(env_value AIOPS_ADMIN_TOKEN)" != "$(env_value AIOPS_INTERNAL_TOKEN)" ]]; then
  echo 'FAIL|internal_token_mismatch|AIOPS_ADMIN_TOKEN_and_AIOPS_INTERNAL_TOKEN_must_match'
  exit 1
fi

if [[ "$MODE" == "1" ]]; then
  echo 'WARN|DEMO_MODE_ENABLED|use only on an isolated local demo; never in production'
  exit 0
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
check_secret AIOPS_PORTAL_READ_TOKEN 'Newaiops26$'
check_secret GLPI_DB_PASSWORD 'Newaiops26$'
check_secret GLPI_DB_ROOT_PASSWORD 'Newaiops26$'
check_secret GRAFANA_ADMIN_PASSWORD 'Newaiops26$'
check_secret N8N_ENCRYPTION_KEY 'Newaiops26$-N8N'

# The optional signed NOC connector is either fully disabled or fully configured.
# Never generate an upstream token/HMAC key here: those must be provisioned out of band.
noc_keys=(AIOPS_NOC_READ_MODEL_URL AIOPS_NOC_READ_MODEL_TOKEN AIOPS_NOC_READ_MODEL_HMAC_KEY AIOPS_NOC_ALLOWED_ORIGINS)
noc_configured=0
for key in "${noc_keys[@]}"; do
  [[ -n "$(env_value "$key")" ]] && noc_configured=1
done
if [[ "$noc_configured" == 0 ]]; then
  echo 'WARN|noc_read_model_unconfigured|GET_api_noc_runtime_state_returns_503'
else
  for key in "${noc_keys[@]}"; do
    if [[ -z "$(env_value "$key")" ]]; then
      echo "FAIL|incomplete_noc_source_configuration|$key"
      failures=1
    fi
  done
  noc_token="$(env_value AIOPS_NOC_READ_MODEL_TOKEN)"
  noc_hmac="$(env_value AIOPS_NOC_READ_MODEL_HMAC_KEY)"
  if [[ ${#noc_token} -lt 16 ]]; then
    echo 'FAIL|noc_upstream_token_too_short'
    failures=1
  fi
  if [[ ! "$noc_token" =~ ^[A-Za-z0-9._~+/-]+=*$ ]]; then
    echo 'FAIL|noc_upstream_token_format_invalid'
    failures=1
  fi
  if [[ ${#noc_hmac} -lt 32 ]]; then
    echo 'FAIL|noc_hmac_key_too_short'
    failures=1
  fi
  if ! python3 - "$ENV_FILE" <<'PY'
import sys
from urllib.parse import urlsplit

values = {}
with open(sys.argv[1], encoding="utf-8") as stream:
    for line in stream:
        line = line.rstrip("\r\n")
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value

def origin(value, endpoint):
    if not value or value.strip() != value:
        raise ValueError
    p = urlsplit(value)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError
    if p.username is not None or p.password is not None or p.query or p.fragment:
        raise ValueError
    if p.netloc != p.netloc.lower():
        raise ValueError
    try:
        p.port
    except ValueError:
        raise ValueError
    if endpoint:
        if not p.path.startswith("/") or p.path == "/" or "\\" in p.path:
            raise ValueError
    elif p.path not in ("", "/"):
        raise ValueError
    return p.scheme + "://" + p.netloc

try:
    endpoint_origin = origin(values.get("AIOPS_NOC_READ_MODEL_URL", ""), True)
    allowed = {
        origin(item.strip(), False)
        for item in values.get("AIOPS_NOC_ALLOWED_ORIGINS", "").split(",")
        if item.strip()
    }
    if endpoint_origin not in allowed:
        raise ValueError
except ValueError:
    print("FAIL|noc_origin_invalid_or_not_allowlisted")
    raise SystemExit(1)
PY
  then
    failures=1
  fi
fi

if [[ "$failures" -ne 0 ]]; then
  echo 'ACTION|use deploy/init-env.sh for a new installation only, or replace every listed value in .env; existing .env files are never rotated automatically'
  exit 1
fi

echo 'SECRET_PREFLIGHT=PASS'
