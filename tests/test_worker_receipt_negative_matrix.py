"""Synthetic-only Worker receipt integrity regression; no host or LIVE effects."""
import asyncio
from copy import deepcopy
from pathlib import Path
import runpy
import unittest

# Reuse the exact independently qualified synthetic PREPARED/Twin/Policy fixtures.
fixture_module = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT = fixture_module["INTENT"]
NOW = fixture_module["NOW"]
fixtures = fixture_module["fixtures"]
simulate_no_effect = fixture_module["simulate_no_effect"]
receipt_digest_valid = fixture_module["receipt_digest_valid"]
verify_no_effect_receipt = fixture_module["verify_no_effect_receipt"]
IDENTITY = {k: INTENT[k] for k in ("attempt_id", "tenant_id", "incident_id", "run_id", "proposal_id", "ticket_id", "approval_id")}


class ReceiptNegativeMatrix(unittest.TestCase):
    def receipt(self):
        docs = fixtures()
        async def get(component, path):
            return deepcopy(docs[component])
        return asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))

    def test_baseline_is_pre_resolution_no_effect(self):
        receipt = self.receipt()
        self.assertTrue(receipt_digest_valid(receipt))
        self.assertTrue(verify_no_effect_receipt(receipt, IDENTITY))
        self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
        self.assertFalse(receipt["resolution_verified"])
        self.assertFalse(receipt["glpi_write"])

    def test_mutation_without_rehash_fails_closed(self):
        baseline = self.receipt()
        for field, value in (
            ("receipt_status", "ALLOW"),
            ("receipt_phase", "POST_RESOLUTION"),
            ("core_status_at_validation", "RESOLVED"),
            ("human_approved", True),
            ("execution_allowed", True),
            ("effect_allowed", True),
            ("glpi_write", True),
            ("effect_receipts", 1),
            ("resolution_verified", True),
            ("post_resolution_readback_required", False),
            ("tenant_id", "FOREIGN"),
            ("run_id", "RUN-OTHER"),
            ("approval_kind", "HUMAN"),
        ):
            receipt = deepcopy(baseline)
            receipt[field] = value
            with self.subTest(field=field):
                self.assertFalse(receipt_digest_valid(receipt))
                self.assertFalse(verify_no_effect_receipt(receipt, IDENTITY))

    def test_parallel_synthetic_receipts_remain_no_effect(self):
        async def batch():
            async def one():
                docs = fixtures()
                async def get(component, path):
                    await asyncio.sleep(0)
                    return deepcopy(docs[component])
                return await simulate_no_effect(INTENT, get=get, now=NOW)
            return await asyncio.gather(*(one() for _ in range(8)))

        receipts = asyncio.run(batch())
        self.assertEqual(len(receipts), 8)
        for receipt in receipts:
            self.assertTrue(receipt_digest_valid(receipt))
            self.assertTrue(verify_no_effect_receipt(receipt, IDENTITY))
            self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
            self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
            self.assertFalse(receipt["glpi_write"])
            self.assertFalse(receipt["resolution_verified"])

    def test_missing_extra_or_invalid_digest_fails_closed(self):
        baseline = self.receipt()
        for mutation in ("missing", "extra", "digest"):
            receipt = deepcopy(baseline)
            if mutation == "missing":
                del receipt["receipt_status"]
            elif mutation == "extra":
                receipt["human_allow"] = True
            else:
                receipt["receipt_sha256"] = "0" * 64
            with self.subTest(mutation=mutation):
                self.assertFalse(receipt_digest_valid(receipt))
                self.assertFalse(verify_no_effect_receipt(receipt, IDENTITY))


if __name__ == "__main__":
    unittest.main()
