"""Worker-owned fail-closed HITL notification tests. No Core endpoint or LIVE."""
import asyncio
import copy
import os
import unittest

from temporalio import workflow

from worker.hitl_reject_notification import (
    UnqualifiedNotification, notify_reject_batch, prepare_reject,
    verify_delivery_ack,
)

HASH = "a" * 64
OWNER = "ci-worker-1"


def snapshot():
    return {
        "execution_allowed": False, "effect_allowed": False,
        "items": [{
            "event_id": "EV-1", "tenant_id": "TEN-SYNTHETIC",
            "run_id": "RUN-SYNTHETIC", "proposal_id": "PR-SYNTHETIC",
            "proposal_hash": HASH, "proposal_revision": 1,
            "lease_token": "LEASE-CI-ONLY", "lease_owner": OWNER,
            "decision": "REJECT", "source_status": "REJECTED",
            "human_approved": False, "execution_allowed": False,
            "effect_allowed": False,
        }],
    }


def ack_receipt(event_id, request, idempotent=False):
    return {
        **{k: request[k] for k in
           ("owner", "tenant_id", "run_id", "proposal_id",
            "proposal_hash", "proposal_revision")},
        "event_id": event_id, "status": "DELIVERED",
        "idempotent": idempotent,
        "execution_allowed": False, "effect_allowed": False,
    }


class RejectNotificationContract(unittest.IsolatedAsyncioTestCase):
    def test_valid_reject_has_no_authorization_or_lease_in_signal(self):
        event_id, run_id, payload, ack = prepare_reject(snapshot(), OWNER)[0]
        self.assertEqual((event_id, run_id), ("EV-1", "RUN-SYNTHETIC"))
        self.assertEqual(payload["decision"], "REJECT")
        self.assertTrue(payload["notification_only"])
        self.assertFalse(payload["execution_allowed"])
        self.assertFalse(payload["effect_allowed"])
        self.assertNotIn("lease_token", payload)
        self.assertEqual(ack["lease_token"], "LEASE-CI-ONLY")

    def test_missing_tenant_owner_hash_revision_fails_closed(self):
        for field, value in (
            ("tenant_id", ""), ("lease_owner", "other"),
            ("proposal_hash", "not-a-digest"),
            ("proposal_revision", True), ("proposal_revision", 0),
            ("run_id", None), ("lease_token", None)):
            with self.subTest(field=field, value=value):
                bad = snapshot()
                bad["items"][0][field] = value
                with self.assertRaises(UnqualifiedNotification):
                    prepare_reject(bad, OWNER)

    def test_no_approval_or_effect_flags(self):
        for field, value in (
            ("decision", "APPROVE"), ("source_status", "APPROVED"),
            ("human_approved", True), ("execution_allowed", True),
            ("effect_allowed", None)):
            with self.subTest(field=field):
                bad = snapshot()
                bad["items"][0][field] = value
                with self.assertRaises(UnqualifiedNotification):
                    prepare_reject(bad, OWNER)

    def test_snapshot_effect_flags_required(self):
        for field, value in (("execution_allowed", None), ("effect_allowed", True)):
            bad = snapshot()
            bad[field] = value
            with self.assertRaises(UnqualifiedNotification):
                prepare_reject(bad, OWNER)

    def test_duplicate_batch_event_refused_before_signal(self):
        bad = snapshot()
        bad["items"].append(copy.deepcopy(bad["items"][0]))
        with self.assertRaises(UnqualifiedNotification):
            prepare_reject(bad, OWNER)

    async def test_signal_failure_never_acknowledges(self):
        calls = []
        async def signal(*args):
            calls.append("signal")
            raise ConnectionError("synthetic Temporal outage")
        async def ack(*args):
            calls.append("ack")
        with self.assertRaises(ConnectionError):
            await notify_reject_batch(snapshot(), owner=OWNER,
                                      signal=signal, acknowledge=ack)
        self.assertEqual(calls, ["signal"])

    async def test_lost_ack_response_is_not_claimed_as_network_proof(self):
        # Synthetic transport exception AFTER fake Core commit; no real network.
        committed = set()
        deliveries = []
        async def signal(run_id, payload):
            deliveries.append((run_id, payload))
        async def ack(event_id, request):
            was_committed = event_id in committed
            committed.add(event_id)
            if len(deliveries) == 1:
                raise ConnectionError("simulated ACK response loss")
            return ack_receipt(event_id, request, idempotent=was_committed)
        with self.assertRaises(ConnectionError):
            await notify_reject_batch(snapshot(), owner=OWNER,
                                      signal=signal, acknowledge=ack)
        receipts = await notify_reject_batch(snapshot(), owner=OWNER,
                                             signal=signal, acknowledge=ack)
        self.assertEqual(len(deliveries), 2)
        self.assertTrue(receipts[0]["idempotent"])
        self.assertFalse(receipts[0]["effect_allowed"])

    def test_ack_must_match_all_bindings(self):
        event_id, _, _, request = prepare_reject(snapshot(), OWNER)[0]
        valid = ack_receipt(event_id, request)
        self.assertEqual(verify_delivery_ack(valid, event_id, request)["status"],
                         "DELIVERED")
        for field, value in (
            ("tenant_id", "FOREIGN"), ("run_id", "FOREIGN"),
            ("proposal_id", "FOREIGN"), ("proposal_hash", "b" * 64),
            ("proposal_revision", 2), ("owner", "other"),
            ("event_id", "OTHER"), ("idempotent", "false"),
            ("execution_allowed", True), ("effect_allowed", None)):
            with self.subTest(field=field):
                bad = {**valid, field: value}
                with self.assertRaises(UnqualifiedNotification):
                    verify_delivery_ack(bad, event_id, request)

    async def test_empty_batch_no_effect(self):
        empty = snapshot()
        empty["items"] = []
        self.assertEqual(prepare_reject(empty, OWNER), [])
        async def forbidden(*args):
            self.fail("transport must not run")
        self.assertEqual(await notify_reject_batch(
            empty, owner=OWNER, signal=forbidden, acknowledge=forbidden), [])


# This is an isolated Temporal SDK development server + actual Temporal Worker
# process lifecycle, NOT Core HTTP and NOT the production IncidentWorkflow.
# The Temporal server itself is not restarted; its restart remains NOT_TESTED.
@workflow.defn(sandboxed=False)
class SyntheticRejectSink:
    def __init__(self):
        self.received = []

    @workflow.run
    async def run(self):
        await workflow.wait_condition(lambda: len(self.received) == 2)
        return self.received

    @workflow.signal
    def reject_notification(self, payload: dict):
        # Signal is notification only, never an authorization.
        if (payload.get("decision") != "REJECT"
                or payload.get("notification_only") is not True
                or payload.get("execution_allowed") is not False
                or payload.get("effect_allowed") is not False):
            raise ValueError("unsafe_temporal_signal")
        self.received.append(payload)

    @workflow.query
    def count(self) -> int:
        return len(self.received)


class RealDisposableTemporalRestart(unittest.IsolatedAsyncioTestCase):
    async def test_real_temporal_worker_restart_reject_only(self):
        if (os.getenv("GITHUB_ACTIONS") != "true"
                or os.getenv("AIOPS_CI_WORKER_DISPOSABLE") != "YES"):
            self.skipTest("real Temporal allowed only on disposable CI")
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        import uuid

        async with await WorkflowEnvironment.start_local() as env:
            queue = "ci-hitl-" + uuid.uuid4().hex
            handle = await env.client.start_workflow(
                SyntheticRejectSink.run, id=queue, task_queue=queue)
            async def signal(run_id, payload):
                self.assertEqual(run_id, "RUN-SYNTHETIC")
                await handle.signal(SyntheticRejectSink.reject_notification, payload)
            async def ack(event_id, request):
                return ack_receipt(event_id, request)
            async with Worker(env.client, task_queue=queue,
                              workflows=[SyntheticRejectSink]):
                first = await notify_reject_batch(snapshot(), owner=OWNER,
                                                   signal=signal, acknowledge=ack)
                self.assertEqual(len(first), 1)
                for _ in range(50):
                    if await handle.query(SyntheticRejectSink.count) == 1:
                        break
                    await asyncio.sleep(0.1)
                else:
                    self.fail("first signal not observed before Worker restart")
            # Worker shut down; new Worker replays the persisted workflow state.
            async with Worker(env.client, task_queue=queue,
                              workflows=[SyntheticRejectSink]):
                second = snapshot()
                second["items"][0]["event_id"] = "EV-2"
                second["items"][0]["source_status"] = "REVOKED"
                await notify_reject_batch(second, owner=OWNER,
                                          signal=signal, acknowledge=ack)
                received = await asyncio.wait_for(handle.result(), timeout=20)
                self.assertEqual([x["event_id"] for x in received], ["EV-1", "EV-2"])
                self.assertTrue(all(x["execution_allowed"] is False
                                    and x["effect_allowed"] is False
                                    for x in received))


if __name__ == "__main__":
    unittest.main()
