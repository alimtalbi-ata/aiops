#!/usr/bin/env bash
set -Eeuo pipefail
BASE_URL="${AIOPS2_BASE_URL:-http://127.0.0.1:18080}"
ENV_FILE="${AIOPS2_ENV_FILE:-/home/aiops/aiops2/.env}"
[[ -f "$ENV_FILE" ]] || { echo "ENV_FILE_MISSING=$ENV_FILE" >&2; exit 2; }
API_KEY="$(sed -n 's/^AIOPS2_API_KEY=//p' "$ENV_FILE" | tail -1)"
[[ -n "$API_KEY" ]] || { echo "API_KEY_MISSING" >&2; exit 3; }
curl --fail --silent --show-error "$BASE_URL/health"; echo
curl --fail --silent --show-error "$BASE_URL/ready"; echo
code="$(curl -sS -o /tmp/aiops2-smoke-unauth.json -w '%{http_code}' "$BASE_URL/v1/incidents")"
[[ "$code" == "401" ]] || { echo "AUTH_GUARD_FAIL status=$code" >&2; exit 4; }
echo "AUTH_GUARD=PASS"
