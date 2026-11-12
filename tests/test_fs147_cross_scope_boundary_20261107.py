"""FS147 scope isolation at each remote boundary (simulated transports only).

This is not an authenticated-host or Core durability qualification.
"""
from datetime import datetime, timezone
from copy import deepcopy
import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_verified_entrypoint import run_fs147_strict

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
SCOPE = dict(tenant_id="tenant-a", actor_id="actor-a", incident_id="incident-a",
             run_id="RUN-147-SCOPE", ticket_id=147)


def observation():
    return dict(SCOPE, evidence_id="EV-147", source="fs-lab-bridge-readonly",
                filesystem="/fs-lab", read_only=True,
                commands=["df", "du", "ls"], collected_at=NOW.isoformat(),
                used_percent=92,
                command_results={
                    "df": dict(exit_code=0, stdout="tmpfs 12M 11M 1M 92% /fs-lab", stderr=""),
                    "du": dict(exit_code=0, stdout="11264 /fs-lab", stderr=""),
                    "ls": dict(exit_code=0, stdout="aiops2-demo-fill.bin", stderr=""),
                })


@pytest.mark.parametrize("stage", ["bridge", "analyst", "critic", "policy"])
@pytest.mark.parametrize("field,value", [
    ("tenant_id", "tenant-b"),
    ("actor_id", "actor-b"),
    ("incident_id", "incident-b"),
    ("run_id", "RUN-OTHER"),
    ("ticket_id", 146),
    ("evidence_id", "EV-OTHER"),
])
def test_cross_scope_response_never_reaches_next_stage_or_replays(stage, field, value):
    calls = []
    reserved = set()
    request = FS147Request("tenant-a", "actor-a", "incident-a", "RUN-147-SCOPE")

    def claim(key):
        calls.append("claim")
        if key in reserved:
            return False
        reserved.add(key)
        return True

    def mutate(payload, at):
        payload = deepcopy(payload)
        if stage == at:
            payload[field] = value
        return payload

    def bridge(payload):
        calls.append("bridge")
        return mutate(observation(), "bridge")

    def analyst(req, obs):
        calls.append("analyst")
        return mutate(dict(SCOPE, evidence_id="EV-147", findings=["92% lab usage"]), "analyst")

    def critic(req, obs, analysis):
        calls.append("critic")
        return mutate(dict(SCOPE, evidence_id="EV-147", state="PASS"), "critic")

    def policy(req, evidence_id, payload):
        calls.append("policy")
        return mutate(dict(SCOPE, evidence_id="EV-147", state="PASS", decision="SIMULATE"), "policy")

    def run():
        return run_fs147_strict(
            request, stop_auto=False, claim_once=claim, bridge_fetch=bridge,
            analyst_call=analyst, critic_call=critic, policy_post=policy,
            now=lambda: NOW)

    result = run()
    expected = ["claim", "bridge", "analyst", "critic", "policy"]
    assert calls == expected[:expected.index(stage) + 1] if stage != "bridge" else calls == expected[:2]
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert result["status"] == "BLOCKED"
    before = list(calls)
    assert run()["reason"] == "DUPLICATE_RUN"
    assert calls == before + ["claim"]
