"""Contract tests: mocked transports are NOT host observations."""
from datetime import datetime, timezone
from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147

NOW = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "RUN-147")


def test_order_stop_and_duplicate():
    calls = []
    identity = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                    run_id="RUN-147", ticket_id=147)
    def claim(key):
        calls.append("claim")
        return True
    def bridge(payload):
        calls.append("bridge")
        assert payload["commands"] == ["df", "du", "ls"]
        return dict(identity, source="fs-lab-bridge-readonly",
                    filesystem="/fs-lab", commands=["df", "du", "ls"],
                    read_only=True, evidence_id="E-147",
                    collected_at=NOW.isoformat(), used_percent=92)
    def analyst(request, observation):
        calls.append("analyst")
        return dict(identity, evidence_id="E-147", findings=["92% used"])
    def critic(request, observation, analysis):
        calls.append("critic")
        return dict(identity, evidence_id="E-147", state="PASS")
    def policy(payload):
        calls.append("policy")
        assert payload["human_approved"] is False
        assert payload["command"] == "OBSERVE"
        return {"state": "PASS", "decision": "SIMULATE"}
    deps = dict(claim_once=claim, bridge_fetch=bridge, analyst_call=analyst,
                critic_call=critic, policy_post=policy, now=lambda: NOW)
    result = run_fs147(REQ, stop_auto=False, **deps)
    assert calls == ["claim", "bridge", "analyst", "critic", "policy"]
    assert result["status"] == "NO_EFFECT" and result["resolved"] is False
    calls.clear()
    assert run_fs147(REQ, stop_auto=True, **deps)["reason"] == "STOP_AUTO"
    assert calls == []
    calls.clear()
    deps["claim_once"] = lambda key: False
    assert run_fs147(REQ, stop_auto=False, **deps)["reason"] == "DUPLICATE_RUN"
    assert calls == []


def test_bridge_unavailable_stops_downstream():
    calls = []
    def unavailable(payload):
        calls.append("bridge")
        raise ConnectionError("offline")
    def forbidden(*args):
        raise AssertionError("downstream called")
    result = run_fs147(REQ, stop_auto=False, claim_once=lambda key: True,
                       bridge_fetch=unavailable, analyst_call=forbidden,
                       critic_call=forbidden, policy_post=forbidden)
    assert result["status"] == "BLOCKED"
    assert result["effect"] == "NO_EFFECT"
    assert calls == ["bridge"]
