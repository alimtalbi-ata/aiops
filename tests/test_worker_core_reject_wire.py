"""Synthetic Worker/Core v1 wire contract. Core #250 is NOT on candidate #234.

The fake post callback is NOT a Core HTTP endpoint, real network ACK loss,
PostgreSQL claim/ACK, or independently authenticated human approval.
"""
import asyncio
import copy
from datetime import datetime, timedelta, timezone
import os
import unittest
import uuid

from worker.hitl_reject_core_wire import (
    CORE_SCHEMA, UnqualifiedNotification, deliver_core_reject_once,
)

TENANT = "TEN-SYNTHETIC"
OWNER = "svc-ci"
HASH = "a" * 64


def claim(event_id="EV-1", *, seconds=30):
    return {
        "schema": CORE_SCHEMA, "status": "LEASED",
        "execution_allowed": False, "effect_allowed": False,
        "items": [{
            "event_id": event_id, "tenant_id": TENANT,
            "run_id": "RUN-SYNTHETIC", "proposal_id": "PR-SYNTHETIC",
            "proposal_hash": HASH, "proposal_revision": 1,
            "lease_owner": OWNER, "lease_token": "x" * 43,
            "lease_until": (datetime.now(timezone.utc)
                            + timedelta(seconds=seconds)).isoformat(),
            "decision": "REJECT", "source_status": "REJECTED",
            "human_approved": False,
            "execution_allowed": False, "effect_allowed": False,
        }],
    }


class SyntheticCorePost:
    """Wire fixture only; never pretends to be an authoritative Core DB."""
    def __init__(self, snapshots):
        self.snapshots = list(snapshots)
        self.calls = []
        self.committed = set()
        self.ack_status = 200
        self.ack_override = {}
        self.lose_response_once = False
        self.claim_status = 200

    async def post(self, path, body):
        self.calls.append((path, copy.deepcopy(body)))
        if path.endswith("/claim"):
            return self.claim_status, copy.deepcopy(self.snapshots.pop(0))
        event_id = path.rsplit("/", 2)[-2]
        was_committed = event_id in self.committed
        self.committed.add(event_id)
        if self.lose_response_once:
            self.lose_response_once = False
            raise ConnectionError("synthetic ACK response exception AFTER fake commit")
        receipt = {
            "schema": CORE_SCHEMA, "status": "DELIVERED",
            "event_id": event_id, "tenant_id": TENANT,
            "run_id": body["run_id"], "proposal_id": body["proposal_id"],
            "proposal_hash": body["proposal_hash"],
            "proposal_revision": body["proposal_revision"],
            "owner": body["owner"], "idempotent": was_committed,
            "execution_allowed": False, "effect_allowed": False,
        }
        receipt.update(self.ack_override)
        return self.ack_status, receipt


class WorkerCoreWireContract(unittest.IsolatedAsyncioTestCase):
    async def test_claim_signal_ack_exact_wire_and_no_effect(self):
        core = SyntheticCorePost([claim()])
        signals = []

        async def signal(run_id, payload):
            signals.append((run_id, payload))

        receipts = await deliver_core_reject_once(
            tenant_id=TENANT, owner=OWNER, post=core.post, signal=signal)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["status"], "DELIVERED")
        self.assertFalse(receipts[0]["execution_allowed"])
        self.assertFalse(receipts[0]["effect_allowed"])
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0][1]["decision"], "REJECT")
        self.assertTrue(signals[0][1]["notification_only"])
        self.assertNotIn("lease_token", signals[0][1])
        self.assertEqual(core.calls[0], (
            f"/api/tenants/{TENANT}/hitl/reject-delivery/claim",
            {"owner": OWNER, "limit": 1}))
        path, body = core.calls[1]
        self.assertEqual(path, f"/api/tenants/{TENANT}/hitl/reject-delivery/EV-1/ack")
        self.assertEqual(set(body), {
            "owner", "run_id", "proposal_id", "proposal_hash",
            "proposal_revision", "lease_token",
            "execution_allowed", "effect_allowed"})
        self.assertNotIn("tenant_id", body)
        self.assertEqual(body["lease_token"], "x" * 43)
        self.assertFalse(body["effect_allowed"])

    async def test_unknown_empty_claim_is_no_work(self):
        empty = claim()
        empty.update(status="UNKNOWN", items=[])
        core = SyntheticCorePost([empty])
        async def forbidden(*args):
            self.fail("no Temporal signal allowed")
        self.assertEqual(await deliver_core_reject_once(
            tenant_id=TENANT, owner=OWNER, post=core.post, signal=forbidden), [])
        self.assertEqual(len(core.calls), 1)

    async def test_expired_naive_missing_lease_never_signals(self):
        bad = []
        old = claim(seconds=-1)
        bad.append(old)
        naive = claim()
        naive["items"][0]["lease_until"] = datetime.now().isoformat()
        bad.append(naive)
        missing = claim()
        del missing["items"][0]["lease_until"]
        bad.append(missing)
        async def forbidden(*args):
            self.fail("invalid lease must not reach Temporal")
        for snapshot in bad:
            with self.subTest(snapshot=snapshot["items"][0].get("lease_until")):
                core = SyntheticCorePost([snapshot])
                with self.assertRaises(UnqualifiedNotification):
                    await deliver_core_reject_once(
                        tenant_id=TENANT, owner=OWNER, post=core.post,
                        signal=forbidden)
                self.assertEqual(len(core.calls), 1)

    async def test_forged_binding_approval_and_effect_never_signal(self):
        cases = (
            ("tenant_id", "FOREIGN"), ("lease_owner", "other"),
            ("proposal_hash", "not-a-sha256"), ("proposal_revision", 0),
            ("decision", "APPROVE"), ("human_approved", True),
            ("effect_allowed", True), ("execution_allowed", True),
        )
        async def forbidden(*args):
            self.fail("invalid claim must not signal")
        for field, value in cases:
            with self.subTest(field=field):
                bad = claim()
                bad["items"][0][field] = value
                core = SyntheticCorePost([bad])
                with self.assertRaises(UnqualifiedNotification):
                    await deliver_core_reject_once(
                        tenant_id=TENANT, owner=OWNER, post=core.post,
                        signal=forbidden)
                self.assertEqual(len(core.calls), 1)

    async def test_core_schema_status_and_http_denial_fail_closed(self):
        async def forbidden(*args):
            self.fail("unqualified Core response must not signal")
        cases = [(401, claim()), (403, claim()), (503, claim())]
        malformed = claim()
        malformed["schema"] = "wrong"
        cases.append((200, malformed))
        unknown = claim()
        unknown["status"] = "UNKNOWN"
        cases.append((200, unknown))
        for status, snapshot in cases:
            with self.subTest(status=status, schema=snapshot["schema"]):
                core = SyntheticCorePost([snapshot])
                core.claim_status = status
                with self.assertRaises(UnqualifiedNotification):
                    await deliver_core_reject_once(
                        tenant_id=TENANT, owner=OWNER, post=core.post,
                        signal=forbidden)

    async def test_invalid_route_tenant_or_owner_never_posts(self):
        core = SyntheticCorePost([claim()])
        async def forbidden(*args):
            self.fail("invalid route must not signal")
        for tenant, owner in (("../TEN", OWNER), (TENANT, "bad/owner"),
                              ("X", OWNER), (TENANT, "")):
            with self.subTest(tenant=tenant, owner=owner):
                with self.assertRaises(UnqualifiedNotification):
                    await deliver_core_reject_once(
                        tenant_id=tenant, owner=owner, post=core.post,
                        signal=forbidden)
        self.assertEqual(core.calls, [])

    async def test_ack_200_without_exact_receipt_is_not_delivery(self):
        for override in ({"status": "UNKNOWN"}, {"idempotent": "true"},
                         {"tenant_id": "FOREIGN"}, {"effect_allowed": True}):
            with self.subTest(override=override):
                core = SyntheticCorePost([claim()])
                core.ack_override = override
                signals = []
                async def signal(*args):
                    signals.append(args)
                with self.assertRaises(UnqualifiedNotification):
                    await deliver_core_reject_once(
                        tenant_id=TENANT, owner=OWNER, post=core.post,
                        signal=signal)
                self.assertEqual(len(signals), 1)
                self.assertEqual(len(core.calls), 2)

    async def test_lost_ack_response_is_only_injected_not_network_loss(self):
        core = SyntheticCorePost([claim()])
        core.lose_response_once = True
        signals = []
        async def signal(*args):
            signals.append(args)
        with self.assertRaises(ConnectionError):
            await deliver_core_reject_once(
                tenant_id=TENANT, owner=OWNER, post=core.post, signal=signal)
        self.assertEqual(len(signals), 1)
        self.assertEqual(core.committed, {"EV-1"})
        # Explicit replay of identical ACK body against fake Core, not a
        # re-claim of a delivered event and not automatic Worker recovery.
        path, body = core.calls[-1]
        code, receipt = await core.post(path, body)
        self.assertEqual(code, 200)
        self.assertTrue(receipt["idempotent"])
        self.assertFalse(receipt["effect_allowed"])


class WorkerCoreTemporalRestart(unittest.IsolatedAsyncioTestCase):
    async def test_disposable_worker_restart_with_synthetic_core_wire(self):
        if (os.getenv("GITHUB_ACTIONS") != "true"
                or os.getenv("AIOPS_CI_WORKER_DISPOSABLE") != "YES"):
            self.skipTest("real Temporal Worker only in disposable CI")
        from temporalio.testing import WorkflowEnvironment
        from temporalio.worker import Worker
        from test_worker_hitl_reject_notification import SyntheticRejectSink

        core = SyntheticCorePost([claim("EV-1"), claim("EV-2")])
        async with await WorkflowEnvironment.start_local() as env:
            queue = "ci-core-wire-" + uuid.uuid4().hex
            handle = await env.client.start_workflow(
                SyntheticRejectSink.run, id=queue, task_queue=queue)
            async def signal(run_id, payload):
                self.assertEqual(run_id, "RUN-SYNTHETIC")
                await handle.signal(SyntheticRejectSink.reject_notification, payload)
            async with Worker(env.client, task_queue=queue,
                              workflows=[SyntheticRejectSink]):
                await deliver_core_reject_once(
                    tenant_id=TENANT, owner=OWNER, post=core.post, signal=signal)
                for _ in range(50):
                    if await handle.query(SyntheticRejectSink.count) == 1:
                        break
                    await asyncio.sleep(0.1)
                else:
                    self.fail("first REJECT not observed before Worker restart")
            async with Worker(env.client, task_queue=queue,
                              workflows=[SyntheticRejectSink]):
                await deliver_core_reject_once(
                    tenant_id=TENANT, owner=OWNER, post=core.post, signal=signal)
                received = await asyncio.wait_for(handle.result(), timeout=20)
                self.assertEqual([x["event_id"] for x in received],
                                 ["EV-1", "EV-2"])
                self.assertTrue(all(
                    x["notification_only"] is True
                    and x["execution_allowed"] is False
                    and x["effect_allowed"] is False for x in received))
        self.assertEqual(len(core.calls), 4)
        self.assertEqual(core.committed, {"EV-1", "EV-2"})


if __name__ == "__main__":
    unittest.main()
