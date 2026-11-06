"""Additional FS147 fail-closed tests. Injected transports are NOT live host proof."""
from datetime import datetime, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147

NOW = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)
REQUEST = FS147Request("tenant", "actor", "incident", "RUN-147-NEGATIVE")
SCOPE = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
             run_id=REQUEST.run_id, ticket_id=147)


def observation():
    return dict(SCOPE, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                commands=["df", "du", "ls"], read_only=True,
                evidence_id="E-147-NEG", collected_at=NOW.isoformat(),
                used_percent=92)


def forbidden(*args, **kwargs):
    raise AssertionError("forbidden downstream invocation")


@pytest.mark.parametrize("missing", ["evidence_id", "collected_at", "used_percent"])
def test_incomplete_bridge_evidence_blocks_before_analyst(missing):
    calls = []
    def bridge(payload):
        calls.append("bridge")
        data = observation()
        del data[missing]
        return data

    result = run_fs147(
        REQUEST, stop_auto=False, claim_once=lambda key: True,
        bridge_fetch=bridge, analyst_call=forbidden,
        critic_call=forbidden, policy_post=forbidden, now=lambda: NOW)
    assert result["status"] == "BLOCKED"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert calls == ["bridge"]


@pytest.mark.parametrize("findings", [[], [""], ["valid", None]])
def test_insufficient_analysis_blocks_before_critic_and_policy(findings):
    calls = []
    def analyst(request, evidence):
        calls.append("analyst")
        return dict(SCOPE, evidence_id="E-147-NEG", findings=findings)

    result = run_fs147(
        REQUEST, stop_auto=False, claim_once=lambda key: True,
        bridge_fetch=lambda payload: observation(), analyst_call=analyst,
        critic_call=forbidden, policy_post=forbidden, now=lambda: NOW)
    assert result["reason"] == "INSUFFICIENT_ANALYSIS"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert calls == ["analyst"]


def test_stop_auto_prevents_claim_and_all_service_calls():
    result = run_fs147(
        REQUEST, stop_auto=True, claim_once=forbidden,
        bridge_fetch=forbidden, analyst_call=forbidden,
        critic_call=forbidden, policy_post=forbidden, now=lambda: NOW)
    assert result["reason"] == "STOP_AUTO"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
