"""FS147 composition regression: injected stubs are not host evidence.

Run: python -m pytest -q tests/test_fs147_service_fail_closed.py
"""
from datetime import datetime, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147


NOW = datetime(2026, 11, 6, 11, 0, tzinfo=timezone.utc)
REQUEST = FS147Request("tenant", "actor", "incident", "RUN-147")


@pytest.fixture
def harness():
    calls = []
    scope = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                 run_id="RUN-147", ticket_id=147)
    def claim(key):
        calls.append("claim")
        return True
    def bridge(payload):
        calls.append("bridge")
        assert payload["filesystem"] == "/fs-lab"
        assert payload["commands"] == ["df", "du", "ls"]
        return dict(scope, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True,
                    evidence_id="E-147", collected_at=NOW.isoformat(),
                    used_percent=92)
    def analyst(request, observation):
        calls.append("analyst")
        return dict(scope, evidence_id="E-147", findings=["fs-lab at 92%"])
    def critic(request, observation, analysis):
        calls.append("critic")
        return dict(scope, evidence_id="E-147", state="PASS")
    def policy(payload):
        calls.append("policy")
        assert payload["command"] == "OBSERVE"
        assert payload["mode"] == "DEMO"
        assert payload["human_approved"] is False
        return {"state": "PASS", "decision": "SIMULATE"}
    deps = dict(claim_once=claim, bridge_fetch=bridge, analyst_call=analyst,
                critic_call=critic, policy_post=policy, now=lambda: NOW)
    return calls, deps, scope


@pytest.mark.parametrize("ack,reason", [
    (False, "DUPLICATE_RUN"),
    (None, "DUPLICATE_RUN"),
    (1, "DUPLICATE_RUN"),
])
def test_duplicate_or_ambiguous_claim_never_observes(harness, ack, reason):
    calls, deps, _ = harness
    deps["claim_once"] = lambda key: ack
    result = run_fs147(REQUEST, stop_auto=False, **deps)
    assert result["reason"] == reason
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
    assert calls == []


@pytest.mark.parametrize("mutation,expected,calls_expected", [
    ("missing_measurement", "INSUFFICIENT_OBSERVATION", ["claim", "bridge"]),
    ("wrong_ticket", "SERVICE_UNAVAILABLE", ["claim", "bridge"]),
    ("empty_findings", "INSUFFICIENT_ANALYSIS", ["claim", "bridge", "analyst"]),
    ("critic_refusal", "CRITIC_REFUSED", ["claim", "bridge", "analyst", "critic"]),
    ("policy_refusal", "POLICY_REFUSED", ["claim", "bridge", "analyst", "critic", "policy"]),
])
def test_fail_closed_and_short_circuit(harness, mutation, expected, calls_expected):
    calls, deps, scope = harness
    if mutation in ("missing_measurement", "wrong_ticket"):
        original = deps["bridge_fetch"]
        def bridge(payload):
            value = original(payload)
            if mutation == "missing_measurement":
                value.pop("used_percent")
            else:
                value["ticket_id"] = 146
            return value
        deps["bridge_fetch"] = bridge
    elif mutation == "empty_findings":
        def analyst(request, observation):
            calls.append("analyst")
            return dict(scope, evidence_id="E-147", findings=[])
        deps["analyst_call"] = analyst
    elif mutation == "critic_refusal":
        def critic(request, observation, analysis):
            calls.append("critic")
            return dict(scope, evidence_id="E-147", state="BLOCKED")
        deps["critic_call"] = critic
    else:
        def policy(payload):
            calls.append("policy")
            return {"state": "BLOCKED", "decision": "DENY"}
        deps["policy_post"] = policy
    result = run_fs147(REQUEST, stop_auto=False, **deps)
    assert result["reason"] == expected
    assert result["status"] == "BLOCKED"
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
    assert calls == calls_expected


def test_stop_auto_has_priority_even_over_core(harness):
    calls, deps, _ = harness
    result = run_fs147(REQUEST, stop_auto=True, **deps)
    assert result["reason"] == "STOP_AUTO"
    assert calls == []


def test_positive_path_is_never_resolution(harness):
    calls, deps, _ = harness
    result = run_fs147(REQUEST, stop_auto=False, **deps)
    assert calls == ["claim", "bridge", "analyst", "critic", "policy"]
    assert result["run_id"] == "RUN-147" and result["ticket_id"] == 147
    assert result["evidence_id"] == "E-147"
    assert result["status"] == "NO_EFFECT" and result["resolved"] is False
