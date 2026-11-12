"""FS147: observation freshness must still hold at the Policy boundary.

All callbacks are stubs. No host observation or Core durability is claimed.
"""
from datetime import datetime, timedelta, timezone

import pytest

from worker.fs147_readonly_pipeline import FS147Request, execute


REQ = FS147Request(tenant_id="tenant", actor_id="actor", incident_id="incident", run_id="run")
T0 = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("elapsed,expected_status,expected_reason,expected_policy_calls", [
    (timedelta(minutes=4, seconds=59), "NO_EFFECT", None, 1),
    (timedelta(minutes=5), "NO_EFFECT", None, 1),
    (timedelta(minutes=5, seconds=1), "BLOCKED", "STALE_OBSERVATION", 0),
    (timedelta(minutes=6), "BLOCKED", "STALE_OBSERVATION", 0),
])
def test_slow_analysis_cannot_forward_expired_evidence_to_policy(
    elapsed, expected_status, expected_reason, expected_policy_calls
):
    clock = [T0]
    calls = {"claim": 0, "observe": 0, "analyst": 0, "critic": 0, "policy": 0}
    scope = dict(tenant_id=REQ.tenant_id, actor_id=REQ.actor_id,
                 incident_id=REQ.incident_id, run_id=REQ.run_id, ticket_id=147)
    observation = dict(scope, evidence_id="evidence", source="fs-lab-bridge-readonly",
                       commands=["df", "du", "ls"], collected_at=T0.isoformat(),
                       used_percent=92, filesystem="/fs-lab", read_only=True)

    def claim(_key):
        calls["claim"] += 1
        return True

    def observe(_request):
        calls["observe"] += 1
        return observation

    def analyst(_request, _observation):
        calls["analyst"] += 1
        clock[0] = T0 + elapsed
        return dict(scope, evidence_id="evidence", findings=["lab usage observed"])

    def critic(_request, _observation, _analysis):
        calls["critic"] += 1
        return dict(scope, evidence_id="evidence", state="PASS")

    def policy(_request, _observation, _analysis, _critique):
        calls["policy"] += 1
        return dict(scope, evidence_id="evidence", state="PASS", decision="SIMULATE")

    result = execute(REQ, stop_auto=False, claim_once=claim, observe=observe,
                     analyst=analyst, critic=critic, policy=policy, now=lambda: clock[0])
    assert result["status"] == expected_status
    assert result.get("reason") == expected_reason
    assert result["effect"] == "NO_EFFECT"
    assert result["resolved"] is False
    assert calls == dict(claim=1, observe=1, analyst=1, critic=1,
                         policy=expected_policy_calls)
