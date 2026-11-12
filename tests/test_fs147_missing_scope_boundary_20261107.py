"""FS147: missing/ill-typed correlation fields fail closed at every boundary.

Simulated callbacks only. No authenticated host, Core durability, or E2E claim.
"""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_verified_entrypoint import run_fs147_strict

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
SCOPE = dict(tenant_id="tenant-a", actor_id="actor-a", incident_id="incident-a",
             run_id="RUN-147-MISSING", ticket_id=147, evidence_id="EV-147")


@pytest.mark.parametrize("stage", ["bridge", "analyst", "critic", "policy"])
@pytest.mark.parametrize("field", list(SCOPE))
@pytest.mark.parametrize("mutation", ["missing", "null"])
def test_missing_or_null_scope_blocks_before_next_service_and_never_replays(stage, field, mutation):
    calls = []
    claimed = set()
    request = FS147Request("tenant-a", "actor-a", "incident-a", "RUN-147-MISSING")

    def claim(key):
        calls.append("claim")
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def inject(data, at):
        data = deepcopy(data)
        if stage == at:
            if mutation == "missing":
                data.pop(field)
            else:
                data[field] = None
        return data

    def bridge(req):
        calls.append("bridge")
        return inject(dict(SCOPE, source="fs-lab-bridge-readonly",
                           filesystem="/fs-lab", read_only=True,
                           commands=["df", "du", "ls"],
                           collected_at=NOW.isoformat(), used_percent=92,
                           command_results={
                               name: dict(exit_code=0, stdout=value, stderr="")
                               for name, value in (
                                   ("df", "tmpfs 12M 11M 1M 92% /fs-lab"),
                                   ("du", "11264 /fs-lab"),
                                   ("ls", "aiops2-demo-fill.bin"))
                           }), "bridge")

    def analyst(req, obs):
        calls.append("analyst")
        return inject(dict(SCOPE, findings=["lab 92%"]), "analyst")

    def critic(req, obs, analysis):
        calls.append("critic")
        return inject(dict(SCOPE, state="PASS"), "critic")

    def policy(req, evidence_id, payload):
        calls.append("policy")
        return inject(dict(SCOPE, state="PASS", decision="SIMULATE"), "policy")

    def run():
        return run_fs147_strict(
            request, stop_auto=False, claim_once=claim, bridge_fetch=bridge,
            analyst_call=analyst, critic_call=critic, policy_post=policy,
            now=lambda: NOW)

    result = run()
    expected = ["claim", "bridge", "analyst", "critic", "policy"]
    assert calls == expected[:expected.index(stage) + 1]
    assert result["status"] == "BLOCKED"
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert result["reason"] == {
        "bridge": "OBSERVATION_SCOPE", "analyst": "ANALYST_SCOPE",
        "critic": "CRITIC_SCOPE", "policy": "POLICY_SCOPE"
    }[stage]
    before = list(calls)
    replay = run()
    assert replay["reason"] == "DUPLICATE_RUN"
    assert replay["effect"] == "NO_EFFECT"
    assert calls == before + ["claim"]
