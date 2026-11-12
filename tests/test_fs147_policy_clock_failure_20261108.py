"""FS147: clock/provider failure at the Policy freshness boundary is fail-closed.

These are deterministic adapter tests, NOT host or authenticated E2E evidence.
No SAN, lab mutation, GLPI write, or Core contract implementation.
"""
from datetime import datetime, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request, execute


T0 = datetime(2026, 11, 8, 0, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "run")


@pytest.mark.parametrize("failure,expected_reason", [
    (TimeoutError("clock timed out"), "UNKNOWN_TIMEOUT"),
    (RuntimeError("clock unavailable"), "SERVICE_UNAVAILABLE"),
])
def test_policy_boundary_clock_failure_blocks_and_consumes_claim(failure, expected_reason):
    scope = dict(tenant_id=REQ.tenant_id, actor_id=REQ.actor_id,
                 incident_id=REQ.incident_id, run_id=REQ.run_id,
                 ticket_id=REQ.ticket_id, evidence_id="evidence")
    claimed = set()
    calls = dict(observe=0, analyst=0, critic=0, policy=0, clock=0)

    def claim(key):
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def observe(request):
        calls["observe"] += 1
        return dict(scope, source="fs-lab-bridge-readonly",
                    commands=["df", "du", "ls"], filesystem="/fs-lab",
                    read_only=True, used_percent=92, collected_at=T0.isoformat())

    def analyst(request, observation):
        calls["analyst"] += 1
        return dict(scope, findings=["observed"])

    def critic(request, observation, analysis):
        calls["critic"] += 1
        return dict(scope, state="PASS")

    def policy(request, observation, analysis, critique):
        calls["policy"] += 1
        return dict(scope, state="PASS", decision="SIMULATE")

    def clock():
        calls["clock"] += 1
        if calls["clock"] == 2:
            raise failure
        return T0

    kwargs = dict(stop_auto=False, claim_once=claim, observe=observe,
                  analyst=analyst, critic=critic, policy=policy, now=clock)
    result = execute(REQ, **kwargs)
    assert result["status"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert calls == dict(observe=1, analyst=1, critic=1, policy=0, clock=2)

    replay = execute(REQ, **kwargs)
    assert replay["status"] == "BLOCKED"
    assert replay["reason"] == "DUPLICATE_RUN"
    assert replay["effect"] == "NO_EFFECT"
    assert replay["resolved"] is False
    assert calls == dict(observe=1, analyst=1, critic=1, policy=0, clock=2)
