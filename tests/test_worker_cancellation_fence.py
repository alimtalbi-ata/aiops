"""Synthetic cancellation fence: cancellation is not a durable rollback proof.

Exercise cancellation at each independent authority read, including the second
readback. No Worker receipt may escape a cancelled attempt. A fresh attempt
must still be limited to PRE_RESOLUTION SIMULATED_NO_EFFECT.
"""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures, simulate_no_effect = base["fixtures"], base["simulate_no_effect"]
receipt_digest_valid = base["receipt_digest_valid"]


class WorkerCancellationFence(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_each_authority_read_without_receipt_then_retry(self):
        for cancel_at in range(1, 7):
            with self.subTest(cancel_at=cancel_at):
                docs = fixtures()
                entered = asyncio.Event()
                release = asyncio.Event()
                reads = []
                emitted = []

                async def paused_get(component, path):
                    reads.append(component)
                    if len(reads) == cancel_at:
                        entered.set()
                        await release.wait()
                    return deepcopy(docs[component])

                async def attempt():
                    emitted.append(await simulate_no_effect(
                        INTENT, get=paused_get, now=NOW))

                task = asyncio.create_task(attempt())
                await asyncio.wait_for(entered.wait(), timeout=2)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=2)
                self.assertEqual(emitted, [])
                self.assertEqual(len(reads), cancel_at)
                self.assertTrue(task.done())
                self.assertTrue(task.cancelled())

                retry_reads = []
                async def fresh_get(component, path):
                    retry_reads.append(component)
                    return deepcopy(docs[component])

                receipt = await simulate_no_effect(INTENT, get=fresh_get, now=NOW)
                self.assertEqual(retry_reads, ["core", "twin", "policy"] * 2)
                self.assertTrue(receipt_digest_valid(receipt))
                self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
                self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
                self.assertIs(receipt["human_approved"], False)
                self.assertIs(receipt["resolution_verified"], False)
                self.assertIs(receipt["glpi_write"], False)
                self.assertEqual(receipt["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
