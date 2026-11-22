"""Pure, deterministic DEMO-only remediation simulator.

This function models a proposed effect in memory. It never performs an action,
claims a Temporal run, or upgrades ITIL/LIVE authorization.
"""
from __future__ import annotations

import hashlib
import json
import re

_ALLOWED = {"SERVICE_RESTART_SIMULATION", "NOOP_OBSERVATION"}
_REQUIRED = {"schema", "mode", "tenant_id", "incident_id", "action_id",
             "action_kind", "before", "policy_decision"}
_BEFORE = {"service", "health", "alert_active"}
_HEALTH = {"DEGRADED", "HEALTHY", "UNKNOWN"}


def _digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def simulate_remediation_dry_run(request: object) -> dict:
    if not isinstance(request, dict) or set(request) != _REQUIRED:
        raise ValueError("invalid_simulation_request_shape")
    if request["schema"] != "aiops.demo-remediation-simulation-request.v1" or request["mode"] != "DEMO":
        raise ValueError("demo_only")
    for field in ("tenant_id", "incident_id", "action_id"):
        value = request[field]
        if (not isinstance(value, str) or not 1 <= len(value) <= 128
                or re.fullmatch(r"[A-Za-z0-9_.:-]+", value) is None):
            raise ValueError("invalid_simulation_identity")
    kind = request["action_kind"]
    if not isinstance(kind, str) or kind not in _ALLOWED:
        raise ValueError("unapproved_simulation_kind")
    if request["policy_decision"] != "SIMULATE_ONLY":
        raise ValueError("simulation_policy_not_qualified")
    before = request["before"]
    if not isinstance(before, dict) or set(before) != _BEFORE:
        raise ValueError("invalid_before_state")
    if (not isinstance(before["service"], str)
            or not 1 <= len(before["service"]) <= 128
            or re.fullmatch(r"[A-Za-z0-9_.:-]+", before["service"]) is None
            or not isinstance(before["health"], str)
            or before["health"] not in _HEALTH
            or type(before["alert_active"]) is not bool):
        raise ValueError("invalid_before_state")
    after = dict(before)
    if kind == "SERVICE_RESTART_SIMULATION":
        # A hypothetical improvement, not a post-check or actual recovery.
        after["health"] = "HEALTHY"
        after["alert_active"] = False
    before_sha = _digest(before)
    after_sha = _digest(after)
    receipt = {
        "schema": "aiops.demo-remediation-simulation-receipt.v1",
        "mode": "DEMO",
        "tenant_id": request["tenant_id"],
        "incident_id": request["incident_id"],
        "action_id": request["action_id"],
        "action_kind": kind,
        "request_sha256": _digest(request),
        "before_sha256": before_sha,
        "after_sha256": after_sha,
        "before": dict(before),
        "hypothetical_after": after,
        "simulation_result": "HYPOTHETICAL_ONLY",
        "runtime_execution_verified": False,
        "independent_postcheck_verified": False,
        "temporal_execution_verified": False,
        "itil_transition_authorized": False,
        "live_remediation_authorized": False,
    }
    return {"receipt": receipt, "receipt_sha256": _digest(receipt)}


def verify_simulation_receipt(request: object, result: object) -> bool:
    """Recompute a deterministic receipt, never trust an asserted after-state."""
    try:
        expected = simulate_remediation_dry_run(request)
        return type(result) is dict and result == expected
    except (ValueError, TypeError, OverflowError):
        return False
