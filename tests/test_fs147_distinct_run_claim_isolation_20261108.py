"""FS147: Core claim must be scoped by run, not merely by GLPI ticket.

Injected-adapter unit test only; does not validate a durable Core reservation.
"""
from datetime import datetime, timezone

from worker.fs147_readonly_pipeline import FS147Request
from worker.fs147_service_pipeline import run_fs147


NOW = datetime(2026, 11, 8, 7, 0, tzinfo=timezone.utc)


def test_two_distinct_runs_share_ticket_but_not_claim_or_evidence():
    claims = set()
    remote_calls = []
    requests = [
        FS147Request("tenant", "actor", "incident", "RUN-147-A"),
        FS147Request("tenant", "actor", "incident", "RUN-147-B"),
    ]

    def claim_once(key):
        if key in claims:
            return False
        claims.add(key)
        return True

    def scoped(request):
        return dict(tenant_id=request.tenant_id, actor_id=request.actor_id,
                    incident_id=request.incident_id, run_id=request.run_id,
                    ticket_id=147, evidence_id="E-" + request.run_id)

    def bridge(request):
        remote_calls.append(("bridge", request.run_id))
        return dict(scoped(request), source="fs-lab-bridge-readonly",
                    filesystem="/fs-lab", commands=["df", "du", "ls"],
                    read_only=True, collected_at=NOW.isoformat(), used_percent=92)

    def analyst(request, observation):
        remote_calls.append(("analyst", request.run_id))
        return dict(scoped(request), findings=["Read-only lab observation"])

    def critic(request, observation, analysis):
        remote_calls.append(("critic", request.run_id))
        return dict(scoped(request), state="PASS")

    def policy(payload):
        remote_calls.append(("policy", payload["run_id"]))
        return dict(state="PASS", decision="SIMULATE")

    dependencies = dict(stop_auto=False, claim_once=claim_once,
                        bridge_fetch=bridge, analyst_call=analyst,
                        critic_call=critic, policy_post=policy, now=lambda: NOW)
    first, second = [run_fs147(request, **dependencies) for request in requests]
    for result, request in zip((first, second), requests):
        assert result["status"] == result["effect"] == "NO_EFFECT"
        assert result["resolved"] is False
        assert result["ticket_id"] == 147
        assert result["run_id"] == request.run_id
        assert result["evidence_id"] == "E-" + request.run_id
    assert len(claims) == 2
    assert len(remote_calls) == 8

    before = list(remote_calls)
    for request in requests:
        replay = run_fs147(request, **dependencies)
        assert replay["status"] == "BLOCKED"
        assert replay["reason"] == "DUPLICATE_RUN"
        assert replay["effect"] == "NO_EFFECT"
        assert replay["resolved"] is False
    assert remote_calls == before
    assert len(claims) == 2
