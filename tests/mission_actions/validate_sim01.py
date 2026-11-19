"""Offline receipt validation only. No HTTP calls or credentials."""
import hashlib
import json
import sys
from pathlib import Path

def validate(journey, result):
    def require(condition, reason):
        if not condition:
            raise ValueError(reason)
    require(journey["schema"] == "aiops.mission-actions.journey.v1", "journey_schema")
    require(journey["mode"] == "DEMO", "journey_mode")
    require(journey["runtime_attested"] is False and journey["live_remediation_authorized"] is False, "journey_authority")
    require(result["schema"] == "aiops.acme-demo-simulation-pipeline.v1", "result_schema")
    require(result["mode"] == "DEMO", "result_mode")
    for key in ("incident_id", "run_id", "source_sha256"):
        require(isinstance(journey[key], str) and bool(journey[key]) and result[key] == journey[key], key)
    require(len(journey["source_sha256"]) == 64 and all(c in "0123456789abcdef" for c in journey["source_sha256"]), "source_digest_format")
    require(result["actual_recovery_state"] == "UNKNOWN", "actual_recovery")
    for key in ("runtime_execution_performed", "glpi_write_performed", "temporal_execution_performed", "live_remediation_authorized"):
        require(result[key] is False, key)
    simulation = result["simulation"]
    receipt = simulation["receipt"]
    digest = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    require(digest == simulation["receipt_sha256"], "receipt_digest")
    require(receipt["incident_id"] == journey["incident_id"], "receipt_incident")
    require(receipt["mode"] == "DEMO" and receipt["simulation_result"] == "HYPOTHETICAL_ONLY", "receipt_mode")
    for key in ("runtime_execution_verified", "independent_postcheck_verified", "temporal_execution_verified", "itil_transition_authorized", "live_remediation_authorized"):
        require(receipt[key] is False, key)
    for key in ("itil_transition_authorized", "live_remediation_authorized"):
        require(result["evidence_gate"][key] is False, "gate_" + key)
    require(receipt["schema"] == "aiops.demo-remediation-simulation-receipt.v1", "receipt_schema")
    require(receipt["tenant_id"] == "acme-demo", "synthetic_tenant")
    require(receipt["action_id"] == "acme-payments-restart-hypothesis-001" and receipt["action_kind"] == "SERVICE_RESTART_SIMULATION", "action_identity")
    before = {"service": "payments", "health": "DEGRADED", "alert_active": True}
    after = {"service": "payments", "health": "HEALTHY", "alert_active": False}
    def sha(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    require(sha(receipt["before"]) == sha(before) == receipt["before_sha256"], "before_state")
    require(sha(receipt["hypothetical_after"]) == sha(after) == receipt["after_sha256"], "after_state")
    request = {"schema": "aiops.demo-remediation-simulation-request.v1", "mode": "DEMO", "tenant_id": "acme-demo", "incident_id": journey["incident_id"], "action_id": receipt["action_id"], "action_kind": receipt["action_kind"], "before": before, "policy_decision": "SIMULATE_ONLY"}
    require(sha(request) == receipt["request_sha256"], "request_digest")
    return "PASS isolated receipt contract; recovery UNKNOWN"

if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("expected journey.json and receipt.json")
        print(validate(*(json.loads(Path(p).read_text()) for p in sys.argv[1:])))
    except (ValueError, KeyError, TypeError, OSError):
        print("FAIL isolated receipt contract", file=sys.stderr)
        sys.exit(1)
