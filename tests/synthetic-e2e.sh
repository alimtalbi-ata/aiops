#!/usr/bin/env bash
set -Eeuo pipefail
BASE=${BASE_URL:-http://127.0.0.1:7777}
BOOTSTRAP_FILE=$(mktemp)
DEMO_FILE=$(mktemp)
trap 'rm -f "$BOOTSTRAP_FILE" "$DEMO_FILE"' EXIT
curl -fsS "$BASE/health" >/dev/null
curl -fsS "$BASE/api/portal/bootstrap" >"$BOOTSTRAP_FILE"
curl -fsS -X POST "$BASE/api/demo" >"$DEMO_FILE"
RUN_ID=$(python3 - "$DEMO_FILE" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    run_id = json.load(f).get("run_id")
if not isinstance(run_id, str) or not run_id.strip():
    raise SystemExit("Demo response missing run_id")
print(run_id)
PY
)
visible=0
for i in $(seq 1 90); do
  curl -fsS "$BASE/api/portal/bootstrap" >"$BOOTSTRAP_FILE"
  if python3 - "$BOOTSTRAP_FILE" "$RUN_ID" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as f:
    data = json.load(f)
def found(value):
    if isinstance(value, dict):
        return value.get("run_id") == sys.argv[2] or any(found(v) for v in value.values())
    if isinstance(value, list):
        return any(found(v) for v in value)
    return False
raise SystemExit(0 if found(data) else 1)
PY
  then
    visible=1
    break
  fi
  sleep 1
done
if [ "$visible" -ne 1 ]; then
  echo "SYNTHETIC_E2E=FAIL|reason=run_not_visible|run=$RUN_ID" >&2
  exit 1
fi
echo "SYNTHETIC_E2E=PASS|run=$RUN_ID"
