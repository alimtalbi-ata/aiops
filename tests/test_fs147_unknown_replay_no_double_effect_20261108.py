"""FS147: indeterminate transport outcomes consume the Core claim.

Pure injected-adapter tests only. No host, SAN, GLPI, or Portal operations.
Run: python -m pytest -q tests/test_fs147_unknown_replay_no_double_effect_20261108.py
"""
from datetime import datetime, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147


NOW = datetime(2026, 11, 8, 5, 0, tzinfo=timezone.utc)
REQUEST = FS147Request("tenant", "actor", "incident", "RUN-147-UNKNOWN")


@pytest.mark.parametrize("failed_stage", ["bridge", "analyst", "critic", "policy"])
@pytest.mark.parametrize("failure,expected", [
    (TimeoutError, "UNKNOWN_TIMEOUT"),
    (ConnectionError, "SERVICE_UNAVAILABLE"),
])
def test_unknown_remote_outcome_is_not_replayed(failed_stage, failure, expected):
    claimed = set()
    calls = []
    scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                 run_id=REQUEST.run_id, ticket_id=147, evidence_id="E-147")

    def claim_once(key):
        calls.append("claim")
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def bridge(payload):
        calls.append("bridge")
        if failed_stage == "bridge":
            raise failure("indeterminate remote outcome")
        return dict(scope, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True,
                    collected_at=NOW.isoformat(), used_percent=92)

    def analyst(request, observation):
        calls.append("analyst")
        if failed_stage == "analyst":
            raise failure("indeterminate remote outcome")
        return dict(scope, findings=["fs-lab measured"])

    def critic(request, observation, analysis):
        calls.append("critic")
        if failed_stage == "critic":
            raise failure("indeterminate remote outcome")
        return dict(scope, state="PASS")

    def policy(payload):
        calls.append("policy")
        if failed_stage == "policy":
            raise failure("indeterminate remote outcome")
        return {"state": "PASS", "decision": "SIMULATE"}

    dependencies = dict(stop_auto=False, claim_once=claim_once,
                        bridge_fetch=bridge, analyst_call=analyst,
                        critic_call=critic, policy_post=policy,
                        now=lambda: NOW)
    first = run_fs147(REQUEST, **dependencies)
    assert first["status"] == "BLOCKED"
    assert first["reason"] == expected
    assert first["effect"] == "NO_EFFECT" and first["resolved"] is False

    before_replay = list(calls)
    replay = run_fs147(REQUEST, **dependencies)
    assert replay["reason"] == "DUPLICATE_RUN"
    assert replay["status"] == "BLOCKED"
    assert replay["effect"] == "NO_EFFECT" and replay["resolved"] is False
    assert calls == before_replay + ["claim"]
    assert len(claimed) == 1
