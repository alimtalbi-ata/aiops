#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE="${BASE_URL:-http://127.0.0.1:7777}"
mkdir -p reports
RUN_ID=""
RESULT="FAIL"
FAILURE="not_completed"
RUN_STATUS="UNKNOWN"
ANALYSIS_COUNT=0
CRITIQUE_COUNT=0
POLICY_COUNT=0
EVIDENCE_COUNT=0
EFFECT_COUNT=0
ANALYSIS_SEVERITY="UNKNOWN"
CRITIQUE_VALIDATED="false"
POLICY_RESULT="UNKNOWN"
EVENT_TYPES=""
DB_USER="$(grep -m1 '^POSTGRES_USER=' .env | cut -d= -f2-)"
DB_NAME="$(grep -m1 '^POSTGRES_DB=' .env | cut -d= -f2-)"
DB_USER="${DB_USER:-aiops}"; DB_NAME="${DB_NAME:-aiops}"
psqlc() { docker compose --env-file .env exec -T aiops2-postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" -Atqc "$1"; }
write_report() {
  RESULT="$RESULT" FAILURE="$FAILURE" RUN_ID="$RUN_ID" RUN_STATUS="$RUN_STATUS" ANALYSIS_COUNT="$ANALYSIS_COUNT" CRITIQUE_COUNT="$CRITIQUE_COUNT" POLICY_COUNT="$POLICY_COUNT" EVIDENCE_COUNT="$EVIDENCE_COUNT" EFFECT_COUNT="$EFFECT_COUNT" ANALYSIS_SEVERITY="$ANALYSIS_SEVERITY" CRITIQUE_VALIDATED="$CRITIQUE_VALIDATED" POLICY_RESULT="$POLICY_RESULT" EVENT_TYPES="$EVENT_TYPES" python3 - <<'PY'
import json, os, pathlib, datetime
p=pathlib.Path("reports")/("runtime-e2e-"+(os.getenv("RUN_ID") or "startup")+".json")
data={
 "qualification":"AIOps 2.0 Temporal synthetic end-to-end",
 "generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
 "result":os.getenv("RESULT","FAIL"),
 "failure_reason":os.getenv("FAILURE",""),
 "run_id":os.getenv("RUN_ID") or None,
 "run_status":os.getenv("RUN_STATUS"),
 "analysis_records":int(os.getenv("ANALYSIS_COUNT","0")),
 "critique_records":int(os.getenv("CRITIQUE_COUNT","0")),
 "policy_decisions":int(os.getenv("POLICY_COUNT","0")),
 "run_evidence_records":int(os.getenv("EVIDENCE_COUNT","0")),
 "effect_receipts":int(os.getenv("EFFECT_COUNT","0")),
 "analysis_severity":os.getenv("ANALYSIS_SEVERITY"),
 "critique_validated":os.getenv("CRITIQUE_VALIDATED")=="true",
 "policy_result":os.getenv("POLICY_RESULT"),
 "event_types":[x for x in os.getenv("EVENT_TYPES","").split(",") if x],
 "mode":"DEMO",
 "live_execution":"disabled",
 "note":"Synthetic CI provider and twin evidence only; this is not real-model or production qualification."
}
p.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
print("RUNTIME_REPORT="+str(p))
PY
}
trap write_report EXIT
curl --retry 10 --retry-connrefused --retry-delay 2 --retry-max-time 30 -fsS "$BASE/health" >/dev/null || { FAILURE="portal_health_unavailable"; exit 1; }
curl --retry 5 --retry-connrefused --retry-delay 2 --retry-max-time 20 -fsS "$BASE/api/portal/bootstrap" >/dev/null || { FAILURE="portal_bootstrap_unavailable"; exit 1; }
curl -fsS -X POST "$BASE/api/demo" -H 'Content-Type: application/json' -d '{}' > /tmp/aiops-runtime-demo.json || { FAILURE="demo_launch_failed"; exit 1; }
RUN_ID="$(python3 -c 'import json; print(json.load(open("/tmp/aiops-runtime-demo.json"))["run_id"])')"
[[ "$RUN_ID" =~ ^[A-Za-z0-9_-]+$ ]] || { FAILURE="invalid_run_id"; exit 1; }
echo "RUN_ID=$RUN_ID"
for i in $(seq 1 180); do
  RUN_STATUS="$(psqlc "select status from aiops.runs where run_id='$RUN_ID'")"
  [[ -n "$RUN_STATUS" ]] || RUN_STATUS="UNKNOWN"
  [[ "$RUN_STATUS" =~ ^(BLOCKED|RESOLVED|FAILED|CANCELLED)$ ]] && break
  sleep 1
done
[[ "$RUN_STATUS" == "BLOCKED" ]] || { FAILURE="expected_P1_policy_block_but_run_status_$RUN_STATUS"; exit 1; }
ANALYSIS_COUNT="$(psqlc "select count(*) from aiops.analysis_records where run_id='$RUN_ID'")"
CRITIQUE_COUNT="$(psqlc "select count(*) from aiops.critique_records where run_id='$RUN_ID'")"
POLICY_COUNT="$(psqlc "select count(*) from aiops.policy_decisions where run_id='$RUN_ID'")"
EVIDENCE_COUNT="$(psqlc "select count(*) from aiops.evidence where provenance->>'run_id'='$RUN_ID'")"
EFFECT_COUNT="$(psqlc "select count(*) from aiops.effect_receipts e join aiops.action_proposals p on p.proposal_id=e.proposal_id where p.run_id='$RUN_ID'")"
ANALYSIS_SEVERITY="$(psqlc "select coalesce(output->>'severity','UNKNOWN') from aiops.analysis_records where run_id='$RUN_ID' order by revision desc limit 1")"
CRITIQUE_VALIDATED="$(psqlc "select coalesce(validated,false)::text from aiops.critique_records where run_id='$RUN_ID' order by created_at desc limit 1")"
POLICY_RESULT="$(psqlc "select coalesce(state,'UNKNOWN')||'|'||coalesce(decision,'UNKNOWN') from aiops.policy_decisions where run_id='$RUN_ID' order by created_at desc limit 1")"
EVENT_TYPES="$(psqlc "select coalesce(string_agg(event_type,',' order by sequence),'') from aiops.run_events where run_id='$RUN_ID'")"
[[ "$ANALYSIS_COUNT" -ge 1 ]] || { FAILURE="analysis_record_missing"; exit 1; }
[[ "$CRITIQUE_COUNT" -ge 1 ]] || { FAILURE="critique_record_missing"; exit 1; }
[[ "$POLICY_COUNT" -ge 1 ]] || { FAILURE="policy_decision_missing"; exit 1; }
[[ "$EVIDENCE_COUNT" -ge 2 ]] || { FAILURE="synthetic_source_evidence_missing"; exit 1; }
[[ "$ANALYSIS_SEVERITY" == "P1" ]] || { FAILURE="expected_P1_classification_got_$ANALYSIS_SEVERITY"; exit 1; }
[[ "$CRITIQUE_VALIDATED" == "true" ]] || { FAILURE="critic_did_not_validate_grounded_fixture"; exit 1; }
[[ "$POLICY_RESULT" == "BLOCKED|ESCALATE" ]] || { FAILURE="expected_blocked_escalation_got_$POLICY_RESULT"; exit 1; }
[[ "$EVENT_TYPES" == *"ANALYST_COMPLETED"* && "$EVENT_TYPES" == *"CRITIC_COMPLETED"* && "$EVENT_TYPES" == *"GATE_BLOCKED"* ]] || { FAILURE="expected_analysis_critic_and_policy_block_events_missing"; exit 1; }
[[ "$EFFECT_COUNT" == "0" ]] || { FAILURE="unexpected_effect_receipt_created_in_synthetic_P1_run"; exit 1; }
RESULT="PASS"
FAILURE=""
echo "RUNTIME_E2E=PASS|run=$RUN_ID|analysis=$ANALYSIS_COUNT|critique=$CRITIQUE_COUNT|policy=$POLICY_RESULT|effects=$EFFECT_COUNT"
