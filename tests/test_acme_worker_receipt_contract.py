"""Offline contract tests; never start Worker, Temporal, or GLPI."""
import unittest

from scripts.acme_worker_receipt_contract import (
    CONSTANTS, FALSE_FLAGS, SCHEMA, TRANSITIONS, TRUE_FLAGS, inspect_worker_receipt,
)

ATTEMPT = "ACME-SIM-" + "A" * 16


def sample():
    result = {"schema": SCHEMA, "attempt_id": ATTEMPT, **CONSTANTS,
              "effect_receipts": 0, "audit_transitions": list(TRANSITIONS)}
    result.update({key: False for key in FALSE_FLAGS})
    result.update({key: True for key in TRUE_FLAGS})
    return result


class WorkerReceiptContractTests(unittest.TestCase):
    def test_valid_structure_not_attestation(self):
        self.assertEqual(inspect_worker_receipt(sample(), ATTEMPT), [])

    def test_missing_and_invalid(self):
        self.assertIn("WORKER_RECEIPT_INVALID", inspect_worker_receipt(None))
        self.assertIn("WORKER_SCHEMA_INVALID", inspect_worker_receipt({"schema": "fake"}))

    def test_wrong_tenant_and_attempt(self):
        receipt = sample()
        receipt["tenant_id"] = "OTHER"
        self.assertIn("WORKER_TENANT_ID_INVALID", inspect_worker_receipt(receipt, ATTEMPT))
        receipt = sample()
        self.assertIn("WORKER_ATTEMPT_MISMATCH",
                      inspect_worker_receipt(receipt, "ACME-SIM-" + "B" * 16))

    def test_live_effects_and_boolean_zero_rejected(self):
        for key in FALSE_FLAGS:
            receipt = sample()
            receipt[key] = 0
            self.assertIn("WORKER_" + key.upper() + "_INVALID",
                          inspect_worker_receipt(receipt, ATTEMPT))
        receipt = sample()
        receipt["effect_receipts"] = False
        self.assertIn("WORKER_EFFECT_RECEIPTS_INVALID",
                      inspect_worker_receipt(receipt, ATTEMPT))

    def test_incomplete_history_and_pre_resolution(self):
        receipt = sample()
        receipt["audit_transitions"] = TRANSITIONS[:-1]
        self.assertIn("WORKER_TRANSITIONS_INVALID", inspect_worker_receipt(receipt))
        receipt = sample()
        receipt["receipt_phase"] = "POST_RESOLUTION"
        self.assertIn("WORKER_RECEIPT_PHASE_INVALID", inspect_worker_receipt(receipt))


if __name__ == "__main__":
    unittest.main()
