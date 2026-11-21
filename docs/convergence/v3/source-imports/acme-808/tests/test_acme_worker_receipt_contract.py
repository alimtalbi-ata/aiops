"""Offline contract tests; never start Worker, Temporal, or GLPI."""
import unittest
import hashlib
import json

from scripts.acme_worker_receipt_contract import (
    CONSTANTS, FALSE_FLAGS, SCHEMA, TRANSITIONS, TRUE_FLAGS, inspect_worker_receipt,
)

ATTEMPT = "ACME-SIM-" + "A" * 16


def sample():
    result = {"schema": SCHEMA, "attempt_id": ATTEMPT, **CONSTANTS,
              "effect_receipts": 0, "audit_transitions": list(TRANSITIONS)}
    result.update({key: False for key in FALSE_FLAGS})
    result.update({key: True for key in TRUE_FLAGS})
    for field, prefix in (("incident_id", "INC-SIM-"),
                          ("run_id", "RUN-SIM-"),
                          ("ticket_id", "SIM-GLPI-"),
                          ("proposal_id", "PROP-SIM-")):
        result[field] = prefix + hashlib.sha256(
            ("ACME-TEST:" + ATTEMPT).encode("ascii")
        ).hexdigest()[:24].upper()
    result["approval_id"] = "SIM-APP-AAAA"
    result['core_request_sha256'] = 'a' * 64
    result['twin_approval_nonce_sha256'] = 'b' * 64
    result['core_source_event_ids'] = ['SYN-EVT-' + hashlib.sha256(
        ('ACME-TEST:' + ATTEMPT + ':' + str(i)).encode('ascii')
    ).hexdigest()[:20].upper() for i in range(1, 8)]
    result['receipt_sha256'] = hashlib.sha256(json.dumps(
        result, sort_keys=True, separators=(',', ':'), ensure_ascii=True
    ).encode('ascii')).hexdigest()
    return result


class WorkerReceiptContractTests(unittest.TestCase):
    def test_valid_structure_not_attestation(self):
        self.assertEqual(inspect_worker_receipt(sample(), ATTEMPT), [])

    def test_rehashed_forged_canonical_run_rejected(self):
        receipt = sample()
        receipt["run_id"] = "RUN-SIM-" + "B" * 24
        receipt["receipt_sha256"] = hashlib.sha256(json.dumps(
            {k: v for k, v in receipt.items() if k != "receipt_sha256"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")).hexdigest()
        self.assertIn("WORKER_RUN_ID_NONCANONICAL",
                      inspect_worker_receipt(receipt))

    def test_missing_approval_identity_rejected(self):
        receipt = sample()
        del receipt["approval_id"]
        self.assertIn("WORKER_APPROVAL_ID_INVALID",
                      inspect_worker_receipt(receipt))

    def test_digest_tamper_is_rejected(self):
        receipt = sample()
        receipt["run_id"] = "FORGED"
        self.assertIn("WORKER_DIGEST_MISMATCH", inspect_worker_receipt(receipt))

    def test_source_ids_must_be_canonical(self):
        receipt = sample()
        receipt["core_source_event_ids"] = ["FAKE"] * 7
        self.assertIn("WORKER_SOURCE_IDS_NONCANONICAL",
                      inspect_worker_receipt(receipt))

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
