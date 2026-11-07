"""FS147 timeout/UNKNOWN and replay safety: injected transports only, no host access."""
from datetime import datetime, timezone
import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147

NOW = datetime(2026, 11, 7, 5, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "RUN-147")
SCOPE = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
             run_id="RUN-147", ticket_id=147)


@pytest.mark.parametrize("timeout_stage", ["bridge", "analyst", "critic", "policy"])
def test_timeout_is_unknown_and_replay_cannot_repeat_effect(timeout_stage):
    calls = []
    claimed = set()

    def claim_once(key):
        calls.append("claim")
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def maybe_timeout(stage):
        calls.append(stage)
        if stage == timeout_stage:
            raise TimeoutError("injected deadline")

    def bridge(payload):
        maybe_timeout("bridge")
        return dict(SCOPE, source="fs-lab-bridge-readonly", filesystem="/fs-lab",
                    commands=["df", "du", "ls"], read_only=True, evidence_id="E-147",
                    collected_at=NOW.isoformat(), used_percent=92)

    def analyst(request, observation):
        maybe_timeout("analyst")
        return dict(SCOPE, evidence_id="E-147", findings=["observed saturation"])

    def critic(request, observation, analysis):
        maybe_timeout("critic")
        return dict(SCOPE, evidence_id="E-147", state="PASS")

    def policy(request, evidence_id, payload):
        maybe_timeout("policy")
        return dict(SCOPE, evidence_id="E-147", state="PASS", decision="SIMULATE")

    def run():
        return run_fs147(
            REQ, stop_auto=False, claim_once=claim_once,
            bridge_fetch=bridge, analyst_call=analyst,
            critic_call=critic, policy_post=policy,
            strict_policy=True, now=lambda: NOW)

    first = run()
    assert first["status"] == "BLOCKED"
    assert first["reason"] == "UNKNOWN_TIMEOUT"
    assert first["effect"] == "NO_EFFECT" and first["resolved"] is False
    snapshot = list(calls)
    second = run()
    assert second["reason"] == "DUPLICATE_RUN"
    assert second["effect"] == "NO_EFFECT" and second["resolved"] is False
    assert calls == snapshot + ["claim"]


def test_stop_auto_prevents_claim_and_all_transports():
    def forbidden(*args, **kwargs):
        raise AssertionError("STOP_AUTO must prevent all calls")
    result = run_fs147(
        REQ, stop_auto=True, claim_once=forbidden, bridge_fetch=forbidden,
        analyst_call=forbidden, critic_call=forbidden, policy_post=forbidden,
        strict_policy=True, now=lambda: NOW)
    assert result["reason"] == "STOP_AUTO"
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
