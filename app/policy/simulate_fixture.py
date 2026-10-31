"""Read-only presentation of an existing Policy SIMULATE decision.

This is an offline fixture, not HITL approval, runtime audit, or an executor.
The adapter calls the existing Policy evaluate() function on a Decision.
"""

from datetime import datetime, timedelta
import re
from typing import Any

from .main import Decision, evaluate

_SAFE_FIXTURE_ACTOR = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")
_SYNTHETIC_MODES = frozenset({"DEMO", "REPLAY", "STORY"})


def _canonical_utc_fixture_timestamp(value: Any) -> bool:
    """Match remediation_lab.iso() output; this is not an observed timestamp."""
    if type(value) is not str:
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return (
        parsed.tzinfo is not None
        and parsed.utcoffset() == timedelta(0)
        and parsed.isoformat() == value
    )


def present_simulate_fixture(
    decision: Decision, *, timestamp: Any, fixture_actor_id: Any
) -> dict[str, Any]:
    """Display a validated synthetic what-if without granting authority.

    Only an existing PASS/SIMULATE Policy decision can be presented. A fixture
    actor is an identifier in sample data, not an authenticated approver.
    """
    if not isinstance(decision, Decision):
        raise ValueError("policy_decision_required")
    mode = decision.mode
    if mode not in _SYNTHETIC_MODES:
        raise ValueError("simulate_mode_required")
    policy_result = evaluate(decision)
    if (
        policy_result.get("state") != "PASS"
        or policy_result.get("decision") != "SIMULATE"
        or type(policy_result.get("reason")) is not str
        or not policy_result["reason"].strip()
    ):
        raise ValueError("policy_not_simulate")
    if not _canonical_utc_fixture_timestamp(timestamp):
        raise ValueError("gate_fixture_timestamp_invalid")
    if type(fixture_actor_id) is not str or not _SAFE_FIXTURE_ACTOR.fullmatch(fixture_actor_id):
        raise ValueError("gate_fixture_actor_invalid")
    return {
        "schema": "aiops.policy-simulate-fixture.v1",
        "classification": "SYNTHETIC_UNVERIFIED",
        "provenance": "WHAT_IF_FIXTURE_NOT_OBSERVED",
        "mode": mode,
        "policy": dict(policy_result),
        "dry_run": True,
        "execution_allowed": False,
        "effect_allowed": False,
        "human": {
            "fixture_actor_id": fixture_actor_id,
            "approval_valid_now": False,
            "authenticated_runtime": False,
        },
        "audit": {
            "fixture_timestamp": timestamp,
            "runtime_verified": False,
            "observed_at": None,
        },
    }
