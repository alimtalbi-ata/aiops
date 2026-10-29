"""Read-only Core synthetic evidence reference adapter contract tests."""
import unittest
from copy import deepcopy

from app.shared.acme_demo_offline import demo_receipt
from app.shared.acme_core_evidence_adapter import normalize_core_evidence_refs


def response(receipt):
    return {
        "schema": "aiops.core-demo-evidence-refs.v1",
        "classification": "SYNTHETIC_ONLY",
        "run_id": receipt["run_id"],
        "tenant_acl_qualified": False,
        "runtime_attested": False,
        "event_link_verified": True,
        "items": [
            {"evidence_id": e, "source": "worker", "payload_sha256": "a" * 64,
             "known_at": "2026-10-29T12:00:00+00:00"}
            for e in receipt["evidence_ids"]
        ],
    }


class CoreEvidenceAdapterTests(unittest.TestCase):
    def setUp(self):
        self.receipt = demo_receipt()
        self.core = response(self.receipt)

    def check_unknown(self, core, reason):
        result = normalize_core_evidence_refs(self.receipt, core)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["reason"], reason)
        self.assertFalse(result["runtime_attested"])
        self.assertFalse(result["evidence_verified"])
        self.assertFalse(result["tenant_acl_qualified"])

    def test_matching_refs_still_not_attested(self):
        result = normalize_core_evidence_refs(self.receipt, self.core)
        self.assertEqual(result["status"], "CONSISTENT_UNATTESTED")
        self.assertEqual(result["matched_evidence_ids"], self.receipt["evidence_ids"])
        self.assertFalse(result["core_run_verified"])
        self.assertFalse(result["effect_applied"])

    def test_missing_response(self):
        self.check_unknown(None, "MISSING_CORE_RESPONSE")

    def test_cross_run(self):
        self.core["run_id"] = "RUN-OTHER"
        self.check_unknown(self.core, "CORE_CONTRACT_MISMATCH")

    def test_claimed_acl_is_rejected(self):
        self.core["tenant_acl_qualified"] = True
        self.check_unknown(self.core, "CORE_CONTRACT_MISMATCH")

    def test_claimed_attestation_is_rejected(self):
        self.core["runtime_attested"] = True
        self.check_unknown(self.core, "CORE_CONTRACT_MISMATCH")

    def test_missing_event_link(self):
        self.core["event_link_verified"] = False
        self.check_unknown(self.core, "CORE_CONTRACT_MISMATCH")

    def test_missing_evidence(self):
        self.core["items"].pop()
        self.check_unknown(self.core, "EVIDENCE_SET_MISMATCH")

    def test_duplicate_evidence(self):
        self.core["items"][1] = deepcopy(self.core["items"][0])
        self.check_unknown(self.core, "EVIDENCE_SET_MISMATCH")

    def test_invalid_payload_digest(self):
        self.core["items"][0]["payload_sha256"] = "bad"
        self.check_unknown(self.core, "CORE_ITEM_UNQUALIFIED")

    def test_invalid_known_at(self):
        self.core["items"][0]["known_at"] = None
        self.check_unknown(self.core, "CORE_ITEM_UNQUALIFIED")

    def test_wrong_schema(self):
        self.core["schema"] = "unknown"
        self.check_unknown(self.core, "CORE_CONTRACT_MISMATCH")

    def test_no_mutation(self):
        receipt = deepcopy(self.receipt)
        core = deepcopy(self.core)
        normalize_core_evidence_refs(self.receipt, self.core)
        self.assertEqual(receipt, self.receipt)
        self.assertEqual(core, self.core)


if __name__ == "__main__":
    unittest.main()
