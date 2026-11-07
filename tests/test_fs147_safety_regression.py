"""FS147 safety regression: no duplicate processing, stale evidence, or execution.

These are deterministic contract tests, NOT evidence of authenticated Debian access.
Run: python -m pytest -q tests/test_fs147_safety_regression.py
"""
from datetime import datetime, timedelta, timezone

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147


NOW = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "RUN-FS147-SAFETY")


def test_duplicate_same_run_claim_blocks_second_pipeline():
    seen = set()
    calls = []
    scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                 run_id=REQ.run_id, ticket_id=147)

    def claim(key):
        if key in seen:
            return False
        seen.add(key)
        return True

    def bridge(payload):
        calls.append("bridge")
        return dict(scope, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True,
                    evidence_id="E-SAFETY", collected_at=NOW.isoformat(),
                    used_percent=92)

    def analyst(request, observation):
        calls.append("analyst")
        return dict(scope, evidence_id="E-SAFETY", findings=["lab usage observed"])

    def critic(request, observation, analysis):
        calls.append("critic")
        return dict(scope, evidence_id="E-SAFETY", state="PASS")

    def policy(payload):
        calls.append("policy")
        return {"state": "PASS", "decision": "SIMULATE"}

    deps = dict(stop_auto=False, claim_once=claim, bridge_fetch=bridge,
                analyst_call=analyst, critic_call=critic, policy_post=policy,
                now=lambda: NOW)
    first = run_fs147(REQ, **deps)
    second = run_fs147(REQ, **deps)
    assert first["status"] == "NO_EFFECT"
    assert second["reason"] == "DUPLICATE_RUN"
    assert calls == ["bridge", "analyst", "critic", "policy"]
    assert first["resolved"] is False and second["resolved"] is False


def test_stale_observation_short_circuits_all_downstream():
    calls = []
    scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                 run_id=REQ.run_id, ticket_id=147)

    def bridge(payload):
        calls.append("bridge")
        return dict(scope, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True,
                    evidence_id="E-OLD",
                    collected_at=(NOW - timedelta(minutes=6)).isoformat(),
                    used_percent=92)

    def forbidden(*args, **kwargs):
        raise AssertionError("downstream service must not be invoked")

    result = run_fs147(REQ, stop_auto=False, claim_once=lambda key: True,
                       bridge_fetch=bridge, analyst_call=forbidden,
                       critic_call=forbidden, policy_post=forbidden,
                       now=lambda: NOW)
    assert result["reason"] == "STALE_OBSERVATION"
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
    assert calls == ["bridge"]


def test_policy_execution_decision_is_refused_without_effect():
    scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                 run_id=REQ.run_id, ticket_id=147)
    def bridge(payload):
        return dict(scope, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True,
                    evidence_id="E-147", collected_at=NOW.isoformat(),
                    used_percent=92)
    def analyst(request, observation):
        return dict(scope, evidence_id="E-147", findings=["observed only"])
    def critic(request, observation, analysis):
        return dict(scope, evidence_id="E-147", state="PASS")
    result = run_fs147(
        REQ, stop_auto=False, claim_once=lambda key: True, bridge_fetch=bridge,
        analyst_call=analyst, critic_call=critic,
        policy_post=lambda payload: {"state": "PASS", "decision": "EXECUTE"},
        now=lambda: NOW)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == "POLICY_REFUSED"
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
