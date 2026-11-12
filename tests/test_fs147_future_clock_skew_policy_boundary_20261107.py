"""FS147: reject observations that become future-dated at the Policy boundary.

Pure adapter tests; not evidence of an authenticated bridge or Debian execution.
No GLPI write, lab mutation, or Core API implementation.
"""
from datetime import datetime, timedelta, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request, execute


T0 = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
REQ = FS147Request("tenant", "actor", "incident", "run")


@pytest.mark.parametrize("future_seconds,expected_policy_calls,expected_reason", [
    (29, 1, None),
    (30, 1, None),
    (31, 0, "STALE_OBSERVATION"),
    (60, 0, "STALE_OBSERVATION"),
])
def test_policy_boundary_rejects_future_clock_skew_and_replay(
    future_seconds, expected_policy_calls, expected_reason
):
    scope = dict(tenant_id=REQ.tenant_id, actor_id=REQ.actor_id,
                 incident_id=REQ.incident_id, run_id=REQ.run_id,
                 ticket_id=REQ.ticket_id, evidence_id="evidence")
    clock = [T0]
    claimed = set()
    calls = dict(claim=0, observe=0, analyst=0, critic=0, policy=0)

    def claim(key):
        calls["claim"] += 1
        if key in claimed:
            return False
        claimed.add(key)
        return True

    def observe(request):
        calls["observe"] += 1
        return dict(scope, source="fs-lab-bridge-readonly",
                    commands=["df", "du", "ls"], filesystem="/fs-lab",
                    read_only=True, used_percent=92,
                    collected_at=T0.isoformat())

    def analyst(request, observation):
        calls["analyst"] += 1
        # Simulate the host clock moving backward while analysis is in flight.
        clock[0] = T0 - timedelta(seconds=future_seconds)
        return dict(scope, findings=["fs-lab inspected"])

    def critic(request, observation, analysis):
        calls["critic"] += 1
        return dict(scope, state="PASS")

    def policy(request, observation, analysis, critique):
        calls["policy"] += 1
        return dict(scope, state="PASS", decision="SIMULATE")

    kwargs = dict(stop_auto=False, claim_once=claim, observe=observe,
                  analyst=analyst, critic=critic, policy=policy,
                  now=lambda: clock[0])
    result = execute(REQ, **kwargs)
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert result["status"] == ("BLOCKED" if expected_reason else "NO_EFFECT")
    assert result.get("reason") == expected_reason
    assert calls == dict(claim=1, observe=1, analyst=1, critic=1,
                         policy=expected_policy_calls)

    replay = execute(REQ, **kwargs)
    assert replay["status"] == "BLOCKED"
    assert replay["reason"] == "DUPLICATE_RUN"
    assert replay["effect"] == "NO_EFFECT"
    assert replay["resolved"] is False
    assert calls == dict(claim=2, observe=1, analyst=1, critic=1,
                         policy=expected_policy_calls)
