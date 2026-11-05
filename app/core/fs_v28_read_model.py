"""Read-only V28 filesystem DEMO contract. Never starts a workflow or grants approval."""
from __future__ import annotations

INCIDENT = "INC-DEMO-FS-001"
RUN = "RUN-4FABD1786F107E51"
SCENARIO = "FS-DEBIAN-SYNTHETIC"
EVIDENCE = "EVD-D2069BA816126499"
TERMINAL = frozenset({"BLOCKED", "BLOCKED_NO_EFFECT", "FAILED", "CANCELLED", "RESOLVED"})
ACTIVE = frozenset({"OBSERVE", "ANALYST", "CRITIC", "POLICY"})


def project(run: dict, evidence: dict, policy: dict | None = None) -> dict:
    """Return a non-authoritative, fail-closed projection; no side effects."""
    base = {"run_id": RUN, "incident_id": INCIDENT, "evidence_id": EVIDENCE,
            "synthetic": True, "live_effects": False, "can_start": False,
            "can_resolve": False, "status": "UNAVAILABLE", "reason": "CONTRACT_MISMATCH"}
    if not isinstance(run, dict) or not isinstance(evidence, dict):
        return base
    if (run.get("run_id") != RUN or run.get("incident_id") != INCIDENT
            or run.get("scenario_id") != SCENARIO or run.get("mode") != "DEMO"
            or evidence.get("evidence_id") != EVIDENCE
            or evidence.get("run_id") != RUN
            or evidence.get("incident_id") != INCIDENT):
        return base
    status = run.get("status")
    if type(status) is not str:
        return {**base, "reason": "INVALID_RUN_STATUS"}
    if status == "CREATED":
        return {**base, "status": "CREATED", "reason": "AWAITING_EXPLICIT_AUTHORIZED_START"}
    if status in ("BLOCKED", "BLOCKED_NO_EFFECT"):
        if not isinstance(policy, dict) or policy.get("state") not in ("BLOCK", "DENY", "BLOCKED"):
            return {**base, "reason": "POLICY_REFUSAL_NOT_ATTESTED"}
        if (policy.get("run_id") != RUN or policy.get("incident_id") != INCIDENT
                or policy.get("live_effects") is not False):
            return base
        return {**base, "status": "BLOCKED_NO_EFFECT", "reason": "POLICY_REFUSED"}
    if status in TERMINAL:
        return {**base, "reason": "TERMINAL_NOT_PROOF_OF_RESOLUTION"}
    if status in ACTIVE:
        return {**base, "status": "IN_PROGRESS", "reason": "NO_AUTHORITY_TO_ADVANCE"}
    return {**base, "reason": "UNKNOWN_RUN_STATUS"}
