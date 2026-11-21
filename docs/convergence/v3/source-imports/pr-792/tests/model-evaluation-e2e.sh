#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
REPORT=reports/ai-core-evaluation.json
[[ -s "$REPORT" ]] || { echo 'FAIL|model_eval_report_missing'; exit 1; }
python3 - "$REPORT" <<'PY'
import json,sys
r=json.load(open(sys.argv[1],encoding="utf-8"))
assert r.get("result")=="PASS", "model evaluation gate failed"
assert r.get("qualification_kind")=="deterministic-integration-fixture", "must be explicitly synthetic"
assert r.get("ledger_persistence",{}).get("status")=="PASS", "not in decision ledger"
assert r.get("gates",{}).get("ledger_persistence") is True, "ledger gate missing"
assert r.get("metrics",{}).get("cases_total")==5
assert r.get("metrics",{}).get("actions_checked",0)>=1
assert r.get("metrics",{}).get("freshness_accuracy")==1.0
assert r.get("metrics",{}).get("contradiction_detection")==1.0
assert r.get("metrics",{}).get("grounding")==1.0
assert r.get("metrics",{}).get("action_safety")==1.0
assert r.get("execution_allowed") is False
assert r.get("persisted_evaluation_id","").startswith("EVAL-")
print("MODEL_EVALUATION_E2E=PASS|evaluation_id="+r["persisted_evaluation_id"])
PY
DB_USER="$(grep -m1 '^POSTGRES_USER=' .env | cut -d= -f2-)"
DB_NAME="$(grep -m1 '^POSTGRES_DB=' .env | cut -d= -f2-)"
DB_USER="${DB_USER:-aiops}"; DB_NAME="${DB_NAME:-aiops}"
EVALUATION_ID="$(python3 -c 'import json;print(json.load(open("reports/ai-core-evaluation.json"))["persisted_evaluation_id"])')"
COUNT="$(docker compose --env-file .env exec -T aiops2-postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atqc "select count(*) from aiops.model_evaluation_runs where evaluation_id='$EVALUATION_ID' and gate_decision='PASS'")"
[[ "$COUNT" == "1" ]] || { echo "FAIL|model_evaluation_ledger_record_missing|$EVALUATION_ID"; exit 1; }
echo "MODEL_EVALUATION_LEDGER=PASS|$EVALUATION_ID"
