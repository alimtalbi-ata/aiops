#!/usr/bin/env bash
set -Eeuo pipefail
BASE=${BASE_URL:-http://127.0.0.1:7777}
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fsS "$BASE/health" >/dev/null
curl -fsS -X POST "$BASE/api/demo" >"$TMP/demo.json"
RUN_ID=$(python3 - "$TMP/demo.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
if not x.get('run_id'):sys.exit('FAIL|NO_RUN_ID')
print(x['run_id'])
PY
)
FOUND=0
for i in $(seq 1 90);do
 curl -fsS "$BASE/api/portal/bootstrap" >"$TMP/state.json"
 if grep -Fq "$RUN_ID" "$TMP/state.json";then FOUND=1;break;fi
 sleep 1
done
[ "$FOUND" = 1 ] || { echo "FAIL|RUN_NOT_VISIBLE|$RUN_ID";exit 1; }
echo "SYNTHETIC_E2E=PASS|run=$RUN_ID"
