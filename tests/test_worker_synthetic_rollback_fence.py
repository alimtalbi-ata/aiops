"""Synthetic rollback/readback fence; NOT a PG16 transaction rollback proof.

A failed attempt must not return a receipt. A subsequent clean attempt is
permitted only as PRE_RESOLUTION / SIMULATED_NO_EFFECT. No LIVE or GLPI effects.
"""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures, simulate_no_effect = base["fixtures"], base["simulate_no_effect"]
SandboxDenied, receipt_digest_valid = base["SandboxDenied"], base["receipt_digest_valid"]


class WorkerSyntheticRollbackFence(unittest.TestCase):
    def test_rollback_to_stale_snapshot_denied_then_clean_retry(self):
        for component, field, stale in (
            ("core", "run_status", "RESOLVED"),
            ("core", "request_sha256", "b" * 64),
            ("twin", "approval_nonce", "NONCE-ROLLED-BACK"),
            ("twin", "approval_status", "REVOKED"),
            ("policy", "decision", "REJECT"),
            ("policy", "state", "BLOCKED"),
        ):
            with self.subTest(component=component, field=field):
                docs = fixtures()
                reads = []
                emitted = []
                async def rollback_get(which, path):
                    reads.append(which)
                    result = deepcopy(docs[which])
                    if len(reads) > 3 and which == component:
                        result[field] = stale
                    return result
                async def failed_attempt():
                    emitted.append(await simulate_no_effect(
                        INTENT, get=rollback_get, now=NOW))
                with self.assertRaises(SandboxDenied):
                    asyncio.run(failed_attempt())
                self.assertEqual(emitted, [])
                self.assertEqual(reads, ["core", "twin", "policy"] * 2)

                async def clean_get(which, path):
                    return deepcopy(docs[which])
                receipt = asyncio.run(simulate_no_effect(
                    INTENT, get=clean_get, now=NOW))
                self.assertTrue(receipt_digest_valid(receipt))
                self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
                self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
                self.assertFalse(receipt["resolution_verified"])
                self.assertFalse(receipt["human_approved"])
                self.assertFalse(receipt["glpi_write"])
                self.assertEqual(receipt["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
