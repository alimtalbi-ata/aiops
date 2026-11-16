#!/usr/bin/env bash
set -Eeuo pipefail
BASE=${BASE_URL:-http://127.0.0.1:7777}
curl -fsS "$BASE/health" >/dev/null
curl -fsS "$BASE/api/portal/bootstrap" >/tmp/aiops-bootstrap.json
curl -fsS -X POST "$BASE/api/demo" >/tmp/aiops-demo.json
RUN_ID=$(python3 -c 'import json; print(json.load(open("/tmp/aiops-demo.json"))["run_id"])')
[ -n "$RUN_ID" ]
for i in $(seq 1 90); do
  J=$(curl -fsS "$BASE/api/portal/bootstrap")
  echo "$J" | grep -q "$RUN_ID" && break
  sleep 1
done
curl -fsS "$BASE/api/portal/bootstrap" >/dev/null
echo "SYNTHETIC_E2E=PASS|run=$RUN_ID"
