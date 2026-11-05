"""Same-key concurrent synthetic readback fence (not durable replay protection).

Two overlapping calls share one attempt/idempotency key. One loses its
independent Policy authority on second read and must fail closed; the other
may only return a synthetic no-effect receipt. This does NOT establish a
PG16 unique constraint, cross-process lease, or Temporal replay fence.
"""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures = base["fixtures"]
simulate_no_effect = base["simulate_no_effect"]
SandboxDenied = base["SandboxDenied"]
receipt_digest_valid = base["receipt_digest_valid"]


class SameKeyOverlapFence(unittest.IsolatedAsyncioTestCase):
    async def test_same_key_overlapping_revocation_denies_only_stale_reader(self):
        docs = fixtures()
        first_reads_done = [asyncio.Event(), asyncio.Event()]
        release_second = asyncio.Event()
        reads = [[], []]
        emitted = [[], []]

        def make_get(index):
            async def get(component, path):
                self.assertTrue(path.endswith(INTENT["attempt_id"]))
                reads[index].append(component)
                if len(reads[index]) == 3:
                    first_reads_done[index].set()
                if len(reads[index]) == 4:
                    await release_second.wait()
                result = deepcopy(docs[component])
                if index == 0 and len(reads[index]) > 3 and component == "policy":
                    result["decision"] = "REJECT"
                return result
            return get

        async def attempt(index):
            receipt = await simulate_no_effect(INTENT, get=make_get(index), now=NOW)
            emitted[index].append(receipt)
            return receipt

        tasks = [asyncio.create_task(attempt(i)) for i in range(2)]
        try:
            await asyncio.wait_for(
                asyncio.gather(*(event.wait() for event in first_reads_done)),
                timeout=5,
            )
            release_second.set()
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True), timeout=5
            )
        finally:
            release_second.set()
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        self.assertIsInstance(results[0], SandboxDenied)
        self.assertEqual(emitted[0], [])
        self.assertEqual(reads[0], ["core", "twin", "policy"] * 2)
        self.assertEqual(reads[1], ["core", "twin", "policy"] * 2)
        self.assertEqual(len(emitted[1]), 1)
        receipt = emitted[1][0]
        self.assertTrue(receipt_digest_valid(receipt))
        self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
        self.assertEqual(receipt["attempt_id"], INTENT["attempt_id"])
        self.assertFalse(receipt["resolution_verified"])
        self.assertFalse(receipt["human_approved"])
        self.assertFalse(receipt["glpi_write"])
        self.assertEqual(receipt["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
