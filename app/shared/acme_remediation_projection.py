"""Deterministic ACME what-if projection. Pure data transformation; NEVER executes effects.

The input simulation must come from the fail-closed remediation_lab gate.
All projected observations are synthetic hypotheses, not real postchecks.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from .remediation_lab import evaluate_simulation

ALLOWED_MODES = frozenset({"DEMO", "REPLAY", "STORY"})
ALLOWED_OUTCOMES = frozenset({"SUCCESS", "FAILURE"})
ALLOWED_HEALTH = frozenset({"HEALTHY", "DEGRADED", "FAILED", "UNKNOWN"})


def project_remediation(
    proposal: dict[str, Any],
    decision: dict[str, Any],
    preconditions: dict[str, bool],
    before: dict[str, Any],
    *,
    outcome: str = "SUCCESS",
    now=None,
) -> dict[str, Any]:
    """Return an auditable before/after/rollback *hypothesis*, without I/O.

    'before' is an explicit fixture, not an observed infrastructure state.
    No actual effect, verification, ticket mutation or rollback takes place.
    """
    if outcome not in ALLOWED_OUTCOMES:
        raise ValueError("unsupported_outcome")
    if not isinstance(before, dict) or set(before) != {"target_ci", "health", "service_available"}:
        raise ValueError("before_schema_invalid")
    if before["target_ci"] != proposal.get("target_ci"):
        raise ValueError("before_target_mismatch")
    if before["health"] not in ALLOWED_HEALTH or type(before["service_available"]) is not bool:
        raise ValueError("before_state_invalid")
    gate = evaluate_simulation(proposal, decision, preconditions, now=now)
    snapshot = deepcopy(before)
    result = {
        "schema_version": 1,
        "synthetic": True,
        "provenance": "WHAT_IF_FIXTURE_NOT_OBSERVED",
        "proposal_id": gate["proposal_id"],
        "proposal_digest": gate["proposal_digest"],
        "target_ci": gate["target_ci"],
        "mode": gate["mode"],
        "recipe_id": gate["recipe_id"],
        "idempotency_key": gate["idempotency_key"],
        "effect_applied": False,
        "postchecks": "NOT_RUN",
        "before": snapshot,
        "after": deepcopy(snapshot),
        "rollback": {"status": "NOT_REQUIRED", "projected_state": deepcopy(snapshot), "effect_applied": False},
        "gate": gate,
    }
    if gate["status"] != "SIMULATED" or proposal["mode"] not in ALLOWED_MODES:
        return {**result, "status": "BLOCKED", "reason": gate.get("reason", "MODE_NOT_ALLOWED")}
    if outcome == "SUCCESS" and gate["recipe_id"] != "ansible-service-restart":
        return {**result, "status": "SIMULATED_NO_RECOVERY", "reason": "RECIPE_NOT_RECOVERY_CAPABLE"}
    if outcome == "FAILURE":
        return {
            **result,
            "status": "SIMULATED_FAILURE",
            "reason": "HYPOTHETICAL_POSTCONDITION_FAILURE",
            "rollback": {
                "status": "PROJECTED_ONLY",
                "projected_state": deepcopy(snapshot),
                "effect_applied": False,
            },
        }
    # Deliberately narrow: a successful hypothetical recovery can only
    # improve the target's synthetic state; it cannot assert a real SLO.
    after = {**snapshot, "health": "HEALTHY", "service_available": True}
    return {
        **result,
        "status": "SIMULATED_SUCCESS",
        "reason": "HYPOTHETICAL_RECOVERY_NOT_VERIFIED",
        "after": after,
        "rollback": {
            "status": "AVAILABLE_AS_PROJECTION",
            "projected_state": deepcopy(snapshot),
            "effect_applied": False,
        },
    }
