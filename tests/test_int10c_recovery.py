"""Offline adaptation of #279 test_08 and #204 interruption cases.
Uses INT09 wire and fixtures; no DB, sockets, Temporal server or authority.
"""
import asyncio
import unittest
from test_int09c_historical_wire import claim, SyntheticCorePost, TENANT, OWNER
from worker.hitl_reject_core_wire import deliver_core_reject_once, UnqualifiedNotification

class RecoveryOffline(unittest.IsolatedAsyncioTestCase):
    async def test_two_contenders_only_claimed_worker_signals(self):
        leased = claim()
        empty = dict(leased, status="UNKNOWN", items=[])
        core = SyntheticCorePost([leased, empty])
        signals = []
        async def signal(run, payload):
            signals.append((run, payload))
        async def contender():
            return await deliver_core_reject_once(tenant_id=TENANT, owner=OWNER,
                                                    post=core.post, signal=signal)
        results = await asyncio.gather(contender(), contender())
        self.assertEqual(sorted(map(len, results)), [0, 1])
        self.assertEqual(len(signals), 1)
        self.assertEqual(len(core.committed), 1)

    async def test_interrupted_signal_then_rotated_claim(self):
        first = claim()
        second = claim()
        second["items"][0]["lease_token"] = "y" * 43
        core = SyntheticCorePost([first, second])
        async def interrupted(*args):
            raise ConnectionError("injected interruption before ACK")
        with self.assertRaises(ConnectionError):
            await deliver_core_reject_once(tenant_id=TENANT, owner=OWNER,
                                            post=core.post, signal=interrupted)
        self.assertEqual(len(core.calls), 1)
        async def resumed(run, payload):
            self.assertNotIn("lease_token", payload)
            self.assertIs(payload["effect_allowed"], False)
        receipts = await deliver_core_reject_once(tenant_id=TENANT, owner=OWNER,
                                                   post=core.post, signal=resumed)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(core.calls[-1][1]["lease_token"], "y" * 43)

    async def test_committed_ack_loss_then_empty_claim_does_not_signal_again(self):
        leased = claim()
        core = SyntheticCorePost([leased, dict(leased, status="UNKNOWN", items=[])])
        core.lose_response_once = True
        signals = []
        async def signal(*args):
            signals.append(args)
        args = dict(tenant_id=TENANT, owner=OWNER, post=core.post, signal=signal)
        with self.assertRaises(ConnectionError):
            await deliver_core_reject_once(**args)
        self.assertEqual(await deliver_core_reject_once(**args), [])
        self.assertEqual(len(signals), 1)
        self.assertEqual(core.committed, {"EV-1"})
