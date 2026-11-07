"""FS147 strict entrypoint contract tests; simulated adapters, no host effects.

These tests do not prove transport authentication or durable Core storage.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_verified_entrypoint import run_fs147_strict

NOW = datetime(2026, 11, 7, 11, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "RUN-147")
SCOPE = dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
             run_id="RUN-147", ticket_id=147)


def evidence():
    return dict(SCOPE, evidence_id="E-147", source="fs-lab-bridge-readonly",
                filesystem="/fs-lab", read_only=True, commands=["df", "du", "ls"],
                collected_at=NOW.isoformat(), used_percent=92,
                command_results={
                    "df": dict(exit_code=0, stdout="tmpfs 12M 11M 1M 92% /fs-lab", stderr=""),
                    "du": dict(exit_code=0, stdout="11264 /fs-lab", stderr=""),
                    "ls": dict(exit_code=0, stdout="aiops2-demo-fill.bin", stderr=""),
                })


def harness(observation=None, *, analyst_reply=None, critic_reply=None,
            policy_reply=None, claim=None):
    calls = []
    claimed = set() if claim is None else claim

    def reserve(key):
        calls.append("claim")
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def bridge(payload):
        calls.append("bridge")
        return deepcopy(observation if observation is not None else evidence())

    def analyst(request, obs):
        calls.append("analyst")
        return deepcopy(analyst_reply if analyst_reply is not None else
                        dict(SCOPE, evidence_id="E-147", findings=["lab usage 92%"]))

    def critic(request, obs, analysis):
        calls.append("critic")
        return deepcopy(critic_reply if critic_reply is not None else
                        dict(SCOPE, evidence_id="E-147", state="PASS"))

    def policy(request, evidence_id, payload):
        calls.append("policy")
        return deepcopy(policy_reply if policy_reply is not None else
                        dict(SCOPE, evidence_id="E-147", state="PASS", decision="SIMULATE"))

    def run():
        return run_fs147_strict(
            REQ, stop_auto=False, claim_once=reserve, bridge_fetch=bridge,
            analyst_call=analyst, critic_call=critic, policy_post=policy,
            now=lambda: NOW)

    return run, calls


@pytest.mark.parametrize("offset,allowed", [
    (timedelta(minutes=5), True),
    (timedelta(minutes=5, microseconds=1), False),
    (timedelta(seconds=-30), True),
    (timedelta(seconds=-30, microseconds=-1), False),
])
def test_freshness_boundaries_and_no_replay(offset, allowed):
    obs = evidence()
    obs["collected_at"] = (NOW - offset).isoformat()
    run, calls = harness(obs)
    result = run()
    if allowed:
        assert calls == ["claim", "bridge", "analyst", "critic", "policy"]
        assert result["status"] == "NO_EFFECT"
    else:
        assert calls == ["claim", "bridge"]
        assert result["reason"] == "STALE_OBSERVATION"
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
    replay = run()
    assert replay["reason"] == "DUPLICATE_RUN"
    assert calls.count("bridge") == 1


@pytest.mark.parametrize("stage,reply,expected,calls_expected", [
    ("analyst", dict(SCOPE, evidence_id="WRONG", findings=["ok"]),
     "ANALYST_SCOPE", ["claim", "bridge", "analyst"]),
    ("analyst", dict(SCOPE, evidence_id="E-147", findings=[]),
     "INSUFFICIENT_ANALYSIS", ["claim", "bridge", "analyst"]),
    ("critic", dict(SCOPE, evidence_id="E-147", state="BLOCKED"),
     "CRITIC_REFUSED", ["claim", "bridge", "analyst", "critic"]),
    ("policy", dict(SCOPE, evidence_id="E-147", state="BLOCKED", decision="BLOCKED"),
     "POLICY_REFUSED", ["claim", "bridge", "analyst", "critic", "policy"]),
    ("policy", dict(SCOPE, evidence_id="E-147", state="PASS", decision="EXECUTE"),
     "POLICY_REFUSED", ["claim", "bridge", "analyst", "critic", "policy"]),
])
def test_fail_closed_stages_and_replay(stage, reply, expected, calls_expected):
    kwargs = {stage + "_reply": reply}
    run, calls = harness(**kwargs)
    result = run()
    assert result["reason"] == expected
    assert calls == calls_expected
    assert result["effect"] == "NO_EFFECT" and result["resolved"] is False
    assert run()["reason"] == "DUPLICATE_RUN"
    assert calls == calls_expected


def test_same_claim_is_scoped_to_run_and_never_reused():
    claimed = set()
    run, calls = harness(claim=claimed)
    assert run()["status"] == "NO_EFFECT"
    assert run()["reason"] == "DUPLICATE_RUN"
    assert len(claimed) == 1
    assert calls.count("bridge") == 1
