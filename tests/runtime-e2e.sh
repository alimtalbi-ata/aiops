#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p reports
REPORT="reports/runtime-e2e-$STAMP.json"
DB_USER="$(grep -m1 '^POSTGRES_USER=' .env | cut -d= -f2-)"
DB_NAME="$(grep -m1 '^POSTGRES_DB=' .env | cut -d= -f2-)"
[[ -n "$DB_USER" ]] || DB_USER=aiops
[[ -n "$DB_NAME" ]] || DB_NAME=aiops
write_report() {
  REPORT_STATUS="$1" REPORT_MESSAGE="$2" REPORT_RUN_ID="${RUN_ID:-}" REPORT_FILE="$REPORT" python3 - <<'PY'
import json, os, datetime
p=os.environ["REPORT_FILE"]
obj={"status":os.environ["REPORT_STATUS"],"message":os.environ["REPORT_MESSAGE"],"run_id":os.environ.get("REPORT_RUN_ID") or None,"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"provider":"deterministic-ci-only","mode":"DEMO"}
open(p,"w",encoding="utf-8").write(json.dumps(obj,indent=2)+"\n")
PY
}
curl -fsS http://127.0.0.1:7777/health >/dev/null || { write_report FAIL portal_health_failed; exit 1; }
bash tests/synthetic-e2e.sh
RUN_ID="$(python3 -c 'import json; print(json.load(open("/tmp/aiops-demo.json"))["run_id"])')"
[[ -n "$RUN_ID" ]] || { write_report FAIL demo_run_id_missing; exit 1; }
DETAIL=""
for i in $(seq 1 180); do
  SQL="select r.status,(select count(*) from aiops.analysis_records a where a.run_id=r.run_id),(select count(*) from aiops.critique_records c where c.run_id=r.run_id),(select count(*) from aiops.policy_decisions p where p.run_id=r.run_id),(select count(*) from aiops.run_events e where e.run_id=r.run_id and e.event_type='INTELLIGENCE_UNAVAILABLE'),(select count(*) from aiops.evidence ev where ev.provenance->>'run_id'=r.run_id and ev.source='twin-simulator' and ev.provenance->>'synthetic'='true'),(select count(*) from aiops.effect_receipts er join aiops.action_proposals ap on ap.proposal_id=er.proposal_id where ap.run_id=r.run_id) from aiops.runs r where r.run_id='$RUN_ID'"
  DETAIL="$(docker compose --env-file .env exec -T aiops2-postgres psql -At -F '|' -U "$DB_USER" -d "$DB_NAME" -c "$SQL" 2>/dev/null || true)"
  if [[ -n "$DETAIL" ]]; then
    IFS='|' read -r STATUS ANALYSES CRITIQUES POLICIES UNAVAILABLE SYNTHETIC_EVIDENCE EFFECTS <<< "$DETAIL"
    if [[ "$STATUS" == RESOLVED || "$STATUS" == BLOCKED || "$STATUS" == FAILED ]]; then break; fi
  fi
  sleep 2
done
if [[ -z "$DETAIL" ]]; then write_report FAIL run_not_found_in_database; exit 1; fi
IFS='|' read -r STATUS ANALYSES CRITIQUES POLICIES UNAVAILABLE SYNTHETIC_EVIDENCE EFFECTS <<< "$DETAIL"
printf 'RUN_STATUS=%s ANALYSES=%s CRITIQUES=%s POLICIES=%s UNAVAILABLE=%s SYNTHETIC_EVIDENCE=%s EFFECTS=%s\n' "$STATUS" "$ANALYSES" "$CRITIQUES" "$POLICIES" "$UNAVAILABLE" "$SYNTHETIC_EVIDENCE" "$EFFECTS"
if [[ "$STATUS" != RESOLVED || "$ANALYSES" -lt 1 || "$CRITIQUES" -lt 1 || "$POLICIES" -lt 1 || "$UNAVAILABLE" -ne 0 || "$SYNTHETIC_EVIDENCE" -lt 2 || "$EFFECTS" -ne 0 ]]; then
  write_report FAIL "core AI ledger or workflow invariant failed: $DETAIL"
  exit 1
fi
REPORT_STATUS=PASS REPORT_MESSAGE="$DETAIL" REPORT_RUN_ID="$RUN_ID" REPORT_FILE="$REPORT" python3 - <<'PY'
import json, os, datetime
p=os.environ["REPORT_FILE"]
obj={"status":os.environ["REPORT_STATUS"],"message":os.environ["REPORT_MESSAGE"],"run_id":os.environ["REPORT_RUN_ID"],"timestamp_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"provider":"deterministic-ci-only","mode":"DEMO","assertions":{"analysis_persisted":True,"critique_persisted":True,"policy_decision_persisted":True,"provider_failures":0,"synthetic_evidence_labelled":True,"real_effects_executed":False}}
open(p,"w",encoding="utf-8").write(json.dumps(obj,indent=2)+"\n")
PY
echo "RUNTIME_E2E=PASS|run=$RUN_ID|report=$REPORT"
