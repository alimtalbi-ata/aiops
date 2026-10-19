#!/usr/bin/env bash
set -Eeuo pipefail
BASE=${BASE_URL:-http://127.0.0.1:7777}
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsS "$BASE/health" >/dev/null
curl -fsS "$BASE/api/portal/bootstrap" >"$TMP/bootstrap-before.json"
curl -fsS -X POST "$BASE/api/demo" >"$TMP/demo-first.json"
RUN_ID="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$TMP/demo-first.json")"
[[ -n "$RUN_ID" ]]
# Repeating the same golden demo must reuse the idempotent incident/run/workflow.
curl -fsS -X POST "$BASE/api/demo" >"$TMP/demo-second.json"
RUN_ID_2="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["run_id"])' "$TMP/demo-second.json")"
[[ "$RUN_ID" == "$RUN_ID_2" ]] || { echo "FAIL|demo_not_idempotent|$RUN_ID|$RUN_ID_2"; exit 1; }
STATUS="UNKNOWN"
for i in $(seq 1 120); do
  curl -fsS "$BASE/api/portal/bootstrap" >"$TMP/bootstrap.json"
  STATUS="$(python3 - "$TMP/bootstrap.json" "$RUN_ID" <<'PY'
import json,sys
data=json.load(open(sys.argv[1]))
rid=sys.argv[2]
for run in data.get("runs",{}).get("items",[]):
    if run.get("run_id")==rid:
        print(run.get("status","UNKNOWN"))
        break
else:
    print("NOT_FOUND")
PY
)"
  case "$STATUS" in
    RESOLVED) break ;;
    BLOCKED|FAILED|CANCELLED)
      echo "FAIL|run_terminal_failure|status=$STATUS|run=$RUN_ID"
      exit 1
      ;;
  esac
  sleep 1
done
[[ "$STATUS" == "RESOLVED" ]] || { echo "FAIL|run_timeout|status=$STATUS|run=$RUN_ID"; exit 1; }
curl -fsS "$BASE/api/portal/runs/$RUN_ID" >"$TMP/run-detail.json"
python3 - "$TMP/run-detail.json" "$RUN_ID" <<'PY'
import json,sys
data=json.load(open(sys.argv[1]))
rid=sys.argv[2]
run=data["run"]
assert run["run_id"] == rid, "wrong run returned"
assert run["mode"] == "DEMO", f"unexpected mode: {run['mode']}"
assert run["status"] == "RESOLVED", f"unexpected terminal status: {run['status']}"
required = ["NORMALIZE","CORRELATE","CMDB","OBSERVE","RAG","DGX_ANALYST","DGX_CRITIC","POLICY","HITL","REMEDIATE","VERIFY","RECONCILE","LEARN"]
stages={item["stage"]:item for item in data.get("stages",[])}
missing=[name for name in required if name not in stages]
assert not missing, f"missing stage rows: {missing}"
bad={name:stages[name].get("state") for name in required if stages[name].get("state") != "PASS"}
assert not bad, f"stages not PASS: {bad}"
gates=data.get("gates",[])
policy=[gate for gate in gates if gate.get("stage")=="POLICY"]
assert policy, "missing POLICY gate"
assert policy[-1].get("state")=="PASS", f"policy gate not PASS: {policy[-1]}"
assert policy[-1].get("decision")=="SIMULATE", f"demo policy was not simulation-only: {policy[-1]}"
completed={event["stage"] for event in data.get("events",[]) if event.get("event_type")=="STAGE_COMPLETED" and event.get("status")=="PASS"}
assert set(required).issubset(completed), f"missing successful stage completion events: {set(required)-completed}"
print(f"E2E_ASSERTIONS=PASS|stages={len(required)}|events={len(data.get('events',[]))}|gates={len(gates)}")
PY
echo "SYNTHETIC_E2E=PASS|run=$RUN_ID|status=$STATUS|idempotency=PASS"
