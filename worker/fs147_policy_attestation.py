"""Fail-closed correlation gate for authenticated FS147 Policy transports.

Use this gate at the transport boundary before the legacy adapter can
normalize missing fields. It is intentionally independent of Core contracts.
"""
from collections.abc import Mapping

FIELDS = ("tenant_id", "actor_id", "incident_id", "run_id", "ticket_id", "evidence_id")


def require_policy_attestation(reply, request, evidence_id):
    """Require every identity field to be attested by the remote Policy reply.

    Never infer remote identity from the outgoing request. UNKNOWN and BLOCKED
    remain legitimate negative decisions; neither authorizes an effect.
    """
    if not isinstance(reply, Mapping):
        raise ValueError("POLICY_UNKNOWN: invalid response")
    expected = {
        "tenant_id": request.tenant_id,
        "actor_id": request.actor_id,
        "incident_id": request.incident_id,
        "run_id": request.run_id,
        "ticket_id": request.ticket_id,
        "evidence_id": evidence_id,
    }
    for name in FIELDS:
        if name not in reply or type(reply[name]) is not type(expected[name]) or reply[name] != expected[name]:
            raise ValueError("POLICY_UNKNOWN: missing or mismatched " + name)
    if reply.get("state") not in ("PASS", "BLOCKED", "UNKNOWN"):
        raise ValueError("POLICY_UNKNOWN: invalid state")
    # A negative state must never carry a contradictory executable decision.
    # In particular BLOCKED/EXECUTE is not a trustworthy refusal.
    if reply.get("decision") not in (None, "SIMULATE", "BLOCK", "REJECT"):
        raise ValueError("POLICY_UNKNOWN: unsafe decision")
    if reply["state"] == "PASS" and reply.get("decision") != "SIMULATE":
        raise ValueError("POLICY_UNKNOWN: unsafe decision")
    if reply["state"] != "PASS" and reply.get("decision") == "SIMULATE":
        raise ValueError("POLICY_UNKNOWN: contradictory negative decision")
    return dict(reply)
