"""FS147: real in-process Policy engine contract, other services stubbed.

This is NOT an authenticated network test or a Debian bridge observation.
Run: python -m pytest -q tests/test_fs147_policy_engine_integration.py
"""
from datetime import datetime, timezone

from app.policy.main import Decision, evaluate
from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147


def test_actual_policy_engine_evaluates_observe_only_without_resolution():
    now = datetime.now(timezone.utc)
    request = FS147Request("tenant", "actor", "incident", "RUN-147-POLICY")
    scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                 run_id=request.run_id, ticket_id=147)
    calls = []

    def claim(_key):
        calls.append("claim")
        return True

    def bridge(payload):
        calls.append("bridge")
        assert payload["commands"] == ["df", "du", "ls"]
        return dict(scope, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True,
                    evidence_id="E-147", used_percent=92,
                    collected_at=now.isoformat())

    def analyst(req, observation):
        calls.append("analyst")
        return dict(scope, evidence_id="E-147", findings=["92% measured in fixture"])

    def critic(req, observation, analysis):
        calls.append("critic")
        return dict(scope, evidence_id="E-147", state="PASS")

    def policy(payload):
        calls.append("policy")
        assert payload["mode"] == "DEMO"
        assert payload["command"] == "OBSERVE"
        assert payload["human_approved"] is False
        assert payload["preconditions_verified"] is False
        return evaluate(Decision(**payload))

    result = run_fs147(request, stop_auto=False, claim_once=claim,
                       bridge_fetch=bridge, analyst_call=analyst,
                       critic_call=critic, policy_post=policy, now=lambda: now)
    assert calls == ["claim", "bridge", "analyst", "critic", "policy"]
    assert result["status"] == "NO_EFFECT"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert result["run_id"] == request.run_id
    assert result["ticket_id"] == 147


def test_actual_policy_engine_refuses_zero_evidence():
    payload = dict(mode="DEMO", command="OBSERVE", severity="UNKNOWN",
                   confidence=0.0, evidence_count=0, critic_validated=True,
                   redundancy_ok=False, evidence_fresh=False,
                   preconditions_verified=False, fencing_verified=False,
                   human_approved=False)
    result = evaluate(Decision(**payload))
    assert result["state"] == "UNKNOWN"
    assert result["decision"] == "HUMAN_APPROVAL"
