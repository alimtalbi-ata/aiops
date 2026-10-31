#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE="${BASE_URL:-http://127.0.0.1:${AIOPS_PORTAL_HOST_PORT:-7777}}"

# Read only the named value from the generated .env; never print or source it.
env_value() {
  local key="$1"
  python3 - "$ROOT/.env" "$key" <<'PY'
import sys
from pathlib import Path
path, key = Path(sys.argv[1]), sys.argv[2]
if not path.is_file():
    raise SystemExit(2)
for line in path.read_text().splitlines():
    if line.startswith(key + "="):
        print(line.split("=", 1)[1])
        raise SystemExit(0)
raise SystemExit(1)
PY
}

DEMO_TOKEN="${AIOPS_PORTAL_OPERATOR_TOKEN:-$(env_value AIOPS_PORTAL_OPERATOR_TOKEN)}"
ENABLED="${AIOPS_SYNTHETIC_DEMO_LAUNCH_ENABLED:-$(env_value AIOPS_SYNTHETIC_DEMO_LAUNCH_ENABLED || true)}"
if [[ "${ENABLED,,}" != "true" ]]; then
  echo "SYNTHETIC_E2E=SKIP|synthetic_demo_launch_disabled"
  exit 0
fi
if [[ -z "$DEMO_TOKEN" ]]; then
  echo "FAIL|portal_operator_token_missing" >&2
  exit 1
fi

curl -fsS "$BASE/health" >/dev/null
KEY="e2e-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RESPONSE="$(curl --fail --silent --show-error -X POST "$BASE/api/demo" \
  -H "Authorization: Bearer $DEMO_TOKEN" \
  -H "Idempotency-Key: $KEY")"
unset DEMO_TOKEN

RUN_ID="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d.get("state")=="STARTED" and d.get("mode")=="DEMO" and d.get("synthetic") is True and d.get("effect_allowed") is False and d.get("live_remediation_authorized") is False; print(d["run_id"])' "$RESPONSE")"
[[ "$RUN_ID" =~ ^RUN-[A-Za-z0-9_.-]+$ ]]
PAGE="$BASE/demo-studio/run/$RUN_ID"
FOUND=0
for i in $(seq 1 90); do
  CODE="$(curl -sS -o /tmp/aiops-demo-run.html -w '%{http_code}' "$PAGE")"
  if [[ "$CODE" == "200" ]] && grep -Fq "$RUN_ID" /tmp/aiops-demo-run.html; then
    FOUND=1
    break
  fi
  sleep 2
done
rm -f /tmp/aiops-demo-run.html
[[ "$FOUND" == "1" ]] || { echo "FAIL|demo_run_not_visible|$RUN_ID" >&2; exit 1; }
echo "SYNTHETIC_E2E=PASS|launch_receipt_and_portal_run_visible|$RUN_ID"
