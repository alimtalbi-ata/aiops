"""Bounded, read-only DEMO Policy gate observation from canonical Core rows.

This projects *persisted* Core/Policy state. It does not call Policy, approve
HITL, execute Temporal, establish tenant ACLs, or attest a remediation.
"""
from __future__ import annotations

import re

from shared.tenant_scope import reject_unqualified_tenant_scope

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{1,95}\Z")
_RUN_STATES = frozenset({
    "CREATED", "RUNNING", "WAITING", "BLOCKED", "RESOLVED", "FAILED", "CANCELLED",
})
# A gate is a stored disposition, never a capability or an effect receipt.
_GATE_PAIRS = frozenset({
    ("PASS", "SIMULATE"),
    ("UNKNOWN", "HUMAN_APPROVAL"),
    ("BLOCKED", "HUMAN_APPROVAL"),
    ("BLOCKED", "ESCALATE"),
})


def project_demo_policy_gate(row: object) -> dict:
    """Reject mismatched/tenant-scoped data rather than inventing an outcome."""
    if not isinstance(row, (tuple, list)) or len(row) != 8:
        raise ValueError("canonical Core row missing")
    run_id, incident_id, mode, status, synthetic, payload, gate_state, decision = row
    if (not isinstance(run_id, str) or _ID.fullmatch(run_id) is None
            or not isinstance(incident_id, str) or _ID.fullmatch(incident_id) is None
            or mode != "DEMO" or status not in _RUN_STATES
            or synthetic is not True or not isinstance(payload, dict)):
        raise ValueError("unqualified DEMO run")
    reject_unqualified_tenant_scope(payload)

    if gate_state is None and decision is None:
        gate_state = "MISSING"
        recorded = False
    elif (gate_state, decision) in _GATE_PAIRS:
        recorded = True
    else:
        raise ValueError("inconsistent persisted Policy gate")

    # These are descriptions of Core records, not causal explanations.
    if status == "BLOCKED":
        explanation = ("BLOCKED_WITHOUT_POLICY_GATE" if not recorded
                       else "BLOCKED_CAUSE_NOT_ESTABLISHED")
    elif status == "RESOLVED":
        explanation = ("RESOLVED_WITH_SIMULATE_GATE_NOT_LIVE"
                       if (gate_state, decision) == ("PASS", "SIMULATE")
                       else "RESOLVED_POLICY_SIMULATION_UNVERIFIED")
    elif status == "RUNNING":
        explanation = "RUNNING_NO_TERMINAL_PROOF"
    else:
        explanation = "RUN_STATE_NOT_REMEDIATION_PROOF"

    return {
        "schema": "aiops.core-demo-policy-observation.v1",
        "run_id": run_id,
        "incident_id": incident_id,
        "mode": "DEMO",
        "run_status": status,
        "policy_gate_state": gate_state,
        "policy_decision": decision,
        "policy_gate_recorded": recorded,
        "explanation_code": explanation,
        "provenance": "CORE_POSTGRES_SYNTHETIC_READ",
        "runtime_attested": False,
        "policy_http_verified": False,
        "hitl_approval_verified": False,
        "temporal_execution_verified": False,
        "postchecks_verified": False,
        "rollback_verified": False,
        "tenant_acl_qualified": False,
        "live_remediation_authorized": False,
    }
