#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE="${BASE_URL:-http://127.0.0.1:${AIOPS_PORTAL_HOST_PORT:-7777}}"

# Read named values only; never source .env, print secrets or enable xtrace.
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

value() {
  local name="$1"
  local fallback="${!name:-}"
  if [[ -n "$fallback" ]]; then printf '%s' "$fallback"; else env_value "$name"; fi
}

DEMO_MODE="$(value AIOPS_DEMO_MODE || true)"
ENABLED="$(value AIOPS_SYNTHETIC_DEMO_LAUNCH_ENABLED || true)"
PROVIDER_KIND="$(value AIOPS_DEMO_PROVIDER_KIND || true)"
LLM_URL="$(value LLM_BASE_URL || true)"
LLM_MODEL_VALUE="$(value LLM_MODEL || true)"
LLM_KEY="$(value LLM_API_KEY || true)"
DEMO_TOKEN="$(value AIOPS_PORTAL_OPERATOR_TOKEN || true)"
if [[ "$DEMO_MODE" != "1" && "${DEMO_MODE,,}" != "true" && "${DEMO_MODE,,}" != "yes" ]]; then
  echo "SYNTHETIC_E2E=BLOCKED|AIOPS_DEMO_MODE_not_enabled" >&2
  exit 1
fi
if [[ "${ENABLED,,}" != "true" ]]; then
  echo "SYNTHETIC_E2E=BLOCKED|synthetic_demo_launch_disabled" >&2
  exit 1
fi
if [[ "$PROVIDER_KIND" != "REAL" || -z "$LLM_URL" || -z "$LLM_MODEL_VALUE" || -z "$LLM_KEY" ]]; then
  unset LLM_KEY DEMO_TOKEN
  echo "SYNTHETIC_E2E=BLOCKED|real_model_provider_not_configured" >&2
  exit 1
fi
if [[ -z "$DEMO_TOKEN" ]]; then
  unset LLM_KEY
  echo "SYNTHETIC_E2E=BLOCKED|portal_operator_token_missing" >&2
  exit 1
fi
unset LLM_KEY

curl -fsS "$BASE/health" >/dev/null
KEY="e2e-$(date -u +%Y%m%dT%H%M%SZ)-$$"
RESPONSE="$(curl --fail --silent --show-error -X POST "$BASE/api/demo" \
  -H "Authorization: Bearer $DEMO_TOKEN" \
  -H "Idempotency-Key: $KEY")"
unset DEMO_TOKEN
RUN_ID="$(python3 -c 'import json,sys; d=json.loads(sys.argv[1]); assert d.get("state")=="STARTED" and d.get("mode")=="DEMO" and d.get("synthetic") is True and d.get("effect_allowed") is False and d.get("live_remediation_authorized") is False; print(d["run_id"])' "$RESPONSE")"
[[ "$RUN_ID" =~ ^RUN-[A-Za-z0-9_.-]+$ ]]

STATUS_JSON=""
TERMINAL=""
for i in $(seq 1 90); do
  STATUS_JSON="$(curl --fail --silent --show-error "$BASE/api/demo-status/$RUN_ID")"
  TERMINAL="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1]).get("status","UNKNOWN"))' "$STATUS_JSON")"
  case "$TERMINAL" in
    RESOLVED|BLOCKED|FAILED|CANCELLED) break ;;
  esac
  sleep 2
done

python3 - "$STATUS_JSON" "$RUN_ID" <<'PY'
import json, sys
data=json.loads(sys.argv[1]); rid=sys.argv[2]
assert data.get("run_id")==rid, "Run identity mismatch"
assert data.get("mode")=="DEMO", "Run mode is not DEMO"
assert data.get("status")=="RESOLVED", "Run did not reach RESOLVED: "+str(data.get("status"))
events=data.get("events")
assert isinstance(events,list), "Core event timeline unavailable"
types={e.get("event_type") for e in events if isinstance(e,dict)}
required={"ANALYST_COMPLETED","CRITIC_COMPLETED","HITL_SIMULATION_SKIPPED"}
missing=required-types
assert not missing, "missing runtime events: "+",".join(sorted(missing))
analyst=next(e for e in events if e.get("event_type")=="ANALYST_COMPLETED")
critic=next(e for e in events if e.get("event_type")=="CRITIC_COMPLETED")
for label,event in (("Analyst",analyst),("Critic",critic)):
    payload=event.get("payload") if isinstance(event.get("payload"),dict) else {}
    invocation=payload.get("model_invocation")
    assert isinstance(invocation,dict) and invocation.get("invocation_id"), label+" provider invocation not attested"
    assert payload.get("provider") and payload.get("model"), label+" provider/model identity missing"
gates=data.get("gates",{}).get("items",[])
policy=[g for g in gates if isinstance(g,dict) and g.get("stage")=="POLICY"]
assert policy and any(g.get("state")=="PASS" and g.get("decision")=="SIMULATE" for g in policy), "Policy SIMULATE gate missing"
assert not any(e.get("event_type") in {"EFFECT_EXECUTED","REMEDIATION_EXECUTED","SSH_COMMAND_EXECUTED"} for e in events if isinstance(e,dict)), "effect event is forbidden in DEMO"
for event in events:
    payload=event.get("payload") if isinstance(event,dict) and isinstance(event.get("payload"),dict) else {}
    assert payload.get("execution_allowed") is not True, "DEMO event attempted to authorize execution"
print("SYNTHETIC_E2E=PASS|real Analyst+Critic|Policy SIMULATE|HITL skipped|no effects|run="+rid)
PY
