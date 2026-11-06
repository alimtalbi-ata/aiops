"""Regression: every FS147 stage must preserve actor and exact ticket identity.

Pure contract tests only. No claim of authenticated Debian E2E.
"""
from datetime import datetime, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request, _matching, execute

REQ = FS147Request("tenant", "actor", "incident", "RUN-147")
NOW = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)


def identity():
    return dict(tenant_id="tenant", actor_id="actor", incident_id="incident",
                run_id="RUN-147", ticket_id=147)


@pytest.mark.parametrize("mutation", [
    {"actor_id": None},
    {"actor_id": "other-actor"},
    {"ticket_id": True},
    {"ticket_id": 147.0},
    {"ticket_id": "147"},
])
def test_exact_identity_rejects_missing_or_coerced_values(mutation):
    value = identity()
    value.update(mutation)
    assert not _matching(value, REQ)


@pytest.mark.parametrize("stage,expected,steps", [
    ("observe", "OBSERVATION_SCOPE", []),
    ("analyst", "ANALYST_SCOPE", ["OBSERVE"]),
    ("critic", "CRITIC_SCOPE", ["OBSERVE", "ANALYST"]),
    ("policy", "POLICY_SCOPE", ["OBSERVE", "ANALYST", "CRITIC"]),
])
def test_missing_actor_fails_closed_before_next_stage(stage, expected, steps):
    calls = []

    def result(which, extra):
        calls.append(which)
        payload = dict(identity(), evidence_id="E-147", **extra)
        if which == stage:
            del payload["actor_id"]
        return payload

    def observe(request):
        return result("observe", dict(source="fs-lab-bridge-readonly",
                   filesystem="/fs-lab", commands=["df", "du", "ls"],
                   read_only=True, collected_at=NOW.isoformat(), used_percent=92))

    def analyst(request, observation):
        return result("analyst", dict(findings=["filesystem usage measured"]))

    def critic(request, observation, analysis):
        return result("critic", dict(state="PASS"))

    def policy(request, observation, analysis, critique):
        return result("policy", dict(state="PASS", decision="SIMULATE"))

    outcome = execute(REQ, stop_auto=False, claim_once=lambda key: True,
                      observe=observe, analyst=analyst, critic=critic,
                      policy=policy, now=lambda: NOW)
    assert outcome["status"] == "BLOCKED"
    assert outcome["effect"] == "NO_EFFECT"
    assert outcome["resolved"] is False
    assert outcome["reason"] == expected
    assert outcome["steps"] == steps
    assert calls == ["observe", "analyst", "critic", "policy"][:len(steps) + 1]
