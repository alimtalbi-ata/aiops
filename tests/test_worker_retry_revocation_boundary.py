"""Synthetic retry/revocation boundary; not a durable PG16 replay guarantee."""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures, simulate_no_effect = base["fixtures"], base["simulate_no_effect"]
SandboxDenied = base["SandboxDenied"]
receipt_digest_valid = base["receipt_digest_valid"]


class WorkerRetryRevocationBoundary(unittest.TestCase):
    def test_revoked_second_read_cannot_emit_receipt_then_clean_retry_is_no_effect(self):
        docs = fixtures()
        calls = []
        async def revoked_get(component, path):
            calls.append(component)
            snapshot = deepcopy(docs[component])
            if len(calls) > 3 and component == "policy":
                snapshot["state"] = "BLOCKED"
            return snapshot
        with self.assertRaises(SandboxDenied):
            asyncio.run(simulate_no_effect(INTENT, get=revoked_get, now=NOW))
        self.assertEqual(calls, ["core", "twin", "policy"] * 2)
        async def clean_get(component, path):
            return deepcopy(docs[component])
        receipt = asyncio.run(simulate_no_effect(INTENT, get=clean_get, now=NOW))
        self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertTrue(receipt_digest_valid(receipt))
        self.assertFalse(receipt["human_approved"])
        self.assertFalse(receipt["glpi_write"])
        self.assertEqual(receipt["effect_receipts"], 0)
        self.assertFalse(receipt["resolution_verified"])

    def test_concurrent_revocation_is_isolated_per_attempt(self):
        async def one(index):
            docs = fixtures()
            reads = 0
            async def get(component, path):
                nonlocal reads
                reads += 1
                snapshot = deepcopy(docs[component])
                if index % 2 and reads > 3 and component == "twin":
                    snapshot["approval_nonce"] = "REVOKED-NONCE"
                await asyncio.sleep(0)
                return snapshot
            try:
                receipt = await simulate_no_effect(INTENT, get=get, now=NOW)
            except SandboxDenied:
                return ("denied", reads)
            return ("receipt", reads, receipt)
        async def run():
            return await asyncio.gather(*(one(i) for i in range(8)))
        results = asyncio.run(run())
        self.assertEqual(len(results), 8)
        for i, result in enumerate(results):
            self.assertEqual(result[1], 6)
            if i % 2:
                self.assertEqual(result[0], "denied")
            else:
                self.assertEqual(result[0], "receipt")
                self.assertTrue(receipt_digest_valid(result[2]))
                self.assertEqual(result[2]["receipt_status"], "SIMULATED_NO_EFFECT")
                self.assertEqual(result[2]["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
