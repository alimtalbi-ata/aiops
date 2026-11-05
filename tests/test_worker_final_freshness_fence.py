"""Final freshness fence: approval must remain valid after both read rounds.

Synthetic-only regression. No PG16/Temporal persistence or human approval implied.
"""
import asyncio
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures = base["fixtures"]
simulate_no_effect = base["simulate_no_effect"]
SandboxDenied = base["SandboxDenied"]
receipt_digest_valid = base["receipt_digest_valid"]


class FinalFreshnessFence(unittest.IsolatedAsyncioTestCase):
    async def test_expiry_after_second_policy_read_denies_without_receipt(self):
        docs = fixtures()
        calls = []
        clock_reads = []
        expiry = NOW + timedelta(minutes=2)

        async def get(component, path):
            self.assertTrue(path.endswith(INTENT["attempt_id"]))
            calls.append(component)
            return deepcopy(docs[component])

        def clock():
            clock_reads.append(len(calls))
            # First and second readback validations succeed. The final
            # post-comparison freshness check must reject expiry.
            return NOW if len(clock_reads) < 3 else expiry + timedelta(seconds=1)

        with self.assertRaises(SandboxDenied):
            await simulate_no_effect(INTENT, get=get, now=clock)
        self.assertEqual(calls, ["core", "twin", "policy"] * 2)
        self.assertEqual(clock_reads, [3, 6, 6])

    async def test_final_fence_before_expiry_emits_only_no_effect(self):
        docs = fixtures()
        calls = []
        clock_reads = []

        async def get(component, path):
            calls.append(component)
            return deepcopy(docs[component])

        def clock():
            clock_reads.append(len(calls))
            return NOW + timedelta(seconds=len(clock_reads))

        receipt = await simulate_no_effect(INTENT, get=get, now=clock)
        self.assertEqual(calls, ["core", "twin", "policy"] * 2)
        self.assertEqual(clock_reads, [3, 6, 6])
        self.assertTrue(receipt_digest_valid(receipt))
        self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
        self.assertFalse(receipt["human_approved"])
        self.assertFalse(receipt["resolution_verified"])
        self.assertFalse(receipt["glpi_write"])
        self.assertEqual(receipt["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
