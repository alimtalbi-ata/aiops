#!/usr/bin/env bash
set -Eeuo pipefail
BASE=${BASE_URL:-http://127.0.0.1:7777}
curl -fsS "$BASE/health" >/dev/null
curl -fsS "$BASE/api/portal/bootstrap" >/dev/null
curl -fsS -X POST "$BASE/api/demo" >/tmp/aiops-demo.json
python3 - <<'PY'
import json
d=json.load(open('/tmp/aiops-demo.json')); assert d.get('run_id'), d; assert d.get('mode')=='DEMO', d
PY
RID=$(python3 -c 'import json; print(json.load(open("/tmp/aiops-demo.json"))["run_id"])')
for i in $(seq 1 120); do
 J=$(curl -fsS "$BASE/api/portal/bootstrap");
 if echo "$J" | grep -q "$RID"; then break; fi; sleep 1;
done
echo "$J" | grep -q "$RID" || { echo 'FAIL|RUN_NOT_VISIBLE'; exit 1; }
# Inspect canonical run directly through the Core endpoint from the Portal network is not exposed; bootstrap is the supported view.
echo "SYNTHETIC_E2E=PASS|run=$RID"
