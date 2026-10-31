"""Disposable-only in-flight Temporal server restart with Core outbox REJECT.

A CI-only sink replays Temporal history after the server restarts. No OIDC
attestation, LIVE approval, executor, or effect. Never run outside test Compose.
"""
import asyncio
import json
import os
import sys
import uuid

import psycopg
from temporalio import workflow
from temporalio.client import Client
from temporalio.worker import Worker

from ci_hitl_outbox_temporal import require_disposable, seed, wait_delivered, read_state


@workflow.defn(name="CIHITLTemporalRestartNoEffectSink", sandboxed=False)
class RestartSink:
    def __init__(self):
        self.decisions = []

    @workflow.signal(name="submit_hitl_decision")
    def observe(self, decision: dict) -> None:
        self.decisions.append(dict(decision))

    @workflow.run
    async def run(self) -> dict:
        await workflow.wait_condition(lambda: len(self.decisions) >= 2, timeout=240)
        return {"decisions": self.decisions, "execution_allowed": False,
                "effect_allowed": False}


QUEUE = "ci-hitl-temporal-restart-sink"


async def prepare(dsn):
    suffix = uuid.uuid4().hex
    run_id = "CI-HITL-RUN-" + suffix
    client = await Client.connect("aiops2-temporal:7233")
    async with Worker(client, task_queue=QUEUE, workflows=[RestartSink]):
        await client.start_workflow(RestartSink.run, id=run_id, task_queue=QUEUE)
        event, proposal, digest = await asyncio.to_thread(seed, dsn, run_id, suffix)
        first = await wait_delivered(dsn, event, proposal, 1)
    # Workflow remains open, awaiting second signal. Worker has exited.
    return {"phase": "PREPARED", "mode": "DEMO", "run_id": run_id,
            "event": event, "proposal": proposal, "digest": digest,
            "first_lease_digest": first[2], "attempts": first[1],
            "identity": "NOT_ATTESTED", "effect_receipts": 0,
            "execution_allowed": False, "effect_allowed": False}


async def resume(dsn, state):
    if (state.get("phase") != "PREPARED" or state.get("mode") != "DEMO"
            or state.get("identity") != "NOT_ATTESTED"
            or state.get("execution_allowed") is not False
            or state.get("effect_allowed") is not False
            or os.getenv("AIOPS_CI_TEMPORAL_RESTARTED_INFLIGHT") != "YES"):
        raise AssertionError("invalid_disposable_restart_attestation")
    run_id, event, proposal, digest = (
        state["run_id"], state["event"], state["proposal"], state["digest"])
    if (not run_id.startswith("CI-HITL-RUN-")
            or not event.startswith("CI-HITL-HDO-")
            or not proposal.startswith("CI-HITL-ACT-")
            or len(digest) != 64):
        raise AssertionError("non_ci_fixture_identity")
    before = await asyncio.to_thread(read_state, dsn, event, proposal)
    if before[0] != "DELIVERED" or before[1] != 1:
        raise AssertionError("unexpected_pre_restart_outbox_state")
    # Controlled synthetic duplicate, NOT proof of actual lost network ACK.
    with psycopg.connect(dsn, connect_timeout=5) as c:
        updated = c.execute(
            "update aiops.hitl_decision_outbox set status='PENDING',"
            "available_at=now(),lease_owner=null,lease_token=null,"
            "lease_until=null,delivered_at=null where event_id=%s "
            "and status='DELIVERED' and attempts=1", (event,))
        if updated.rowcount != 1:
            raise AssertionError("ci_replay_not_queued")
    client = await Client.connect("aiops2-temporal:7233")
    handle = client.get_workflow_handle(run_id)
    async with Worker(client, task_queue=QUEUE, workflows=[RestartSink]):
        result = await asyncio.wait_for(handle.result(), timeout=180)
        second = await wait_delivered(dsn, event, proposal, 2)
    expected = {"proposal_id": proposal, "proposal_hash": digest,
                "proposal_revision": 1, "decision": "REJECT",
                "source_status": "REJECTED"}
    if result["decisions"] != [expected, expected]:
        raise AssertionError("temporal_history_replay_or_signal_mismatch")
    if result["execution_allowed"] is not False or result["effect_allowed"] is not False:
        raise AssertionError("effect_fence_invalid")
    if (state["first_lease_digest"] == second[2]
            or len(str(second[2])) != 64):
        raise AssertionError("lease_fencing_invalid")
    return {"result": "PASS", "mode": "DEMO",
            "scope": "Core outbox -> Worker -> Temporal CI sink -> Core ACK",
            "identity": "NOT_ATTESTED", "human_approval": "NOT_TESTED",
            "production_incident_workflow": "NOT_TESTED",
            "run_id": run_id, "outbox_event": event,
            "outbox_state": second[0], "attempts": second[1],
            "temporal_signals": len(result["decisions"]),
            "replay": "CI_SYNTHETIC_REQUEUE_NOT_REAL_LOST_ACK",
            "temporal_server_restart_inflight": "OBSERVED_CI_DISPOSABLE",
            "ci_sink_worker_restart_inflight": "OBSERVED",
            "production_worker_restart_inflight": "NOT_TESTED",
            "effect_receipts": 0, "execution_allowed": False,
            "effect_allowed": False}


async def main():
    dsn = require_disposable()
    if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "resume"):
        raise RuntimeError("require_explicit_ci_phase")
    if sys.argv[1] == "prepare":
        report = await prepare(dsn)
    else:
        report = await resume(dsn, json.load(sys.stdin))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
