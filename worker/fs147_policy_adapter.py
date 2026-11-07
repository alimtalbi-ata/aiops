"""FS147 adapter for the existing authenticated /api/policy/check endpoint.

The host injects the authenticated transport. No remediation or HITL is performed.
"""
from collections.abc import Mapping


def check_fs147_policy(request, observation, analysis, critique, *, post_check):
    """Send OBSERVE-only policy request, binding the reply to the current run.

    post_check(payload) must call the actual Policy endpoint with authenticated
    transport; transport errors propagate and the Worker must fail closed.
    """
    if (request.mode != "DEMO" or request.ticket_id != 147
            or critique.get("state") != "PASS"
            or observation.get("evidence_id") != analysis.get("evidence_id")
            or observation.get("evidence_id") != critique.get("evidence_id")):
        raise ValueError("invalid FS147 policy preconditions")
    payload = {
        "mode": "DEMO", "command": "OBSERVE", "severity": "UNKNOWN",
        "confidence": 0.0, "evidence_count": 1,
        "critic_validated": True, "redundancy_ok": False,
        "evidence_fresh": True, "preconditions_verified": False,
        "fencing_verified": False, "human_approved": False,
    }
    result = post_check(payload)
    if not isinstance(result, Mapping) or result.get("state") not in ("PASS", "BLOCKED", "UNKNOWN"):
        raise ValueError("invalid policy response")
    # Reject any explicit contradiction, even if legacy Policy omits correlation.
    expected = {
        "tenant_id": request.tenant_id, "actor_id": request.actor_id,
        "incident_id": request.incident_id, "run_id": request.run_id,
        "ticket_id": request.ticket_id, "evidence_id": observation["evidence_id"],
    }
    for field, value in expected.items():
        if field in result and (type(result[field]) is not type(value) or result[field] != value):
            raise ValueError("policy response correlation mismatch: " + field)
    # Missing correlation is not proof; authentication remains transport-owned.
    return {
        "tenant_id": request.tenant_id, "actor_id": request.actor_id,
        "incident_id": request.incident_id, "run_id": request.run_id,
        "ticket_id": request.ticket_id, "evidence_id": observation["evidence_id"],
        "state": result["state"], "decision": result.get("decision"),
        "reason": result.get("reason"),
    }
