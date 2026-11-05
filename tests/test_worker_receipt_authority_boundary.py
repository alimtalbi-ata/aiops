"""Receipt digest integrity is not an authorization or anti-replay proof.

Synthetic-only contract tests. No database, Temporal, GLPI, or human approval.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import runpy
import unittest

base = runpy.run_path(str(Path(__file__).with_name("test_worker_acme_simulated_hitl.py")))
INTENT, NOW = base["INTENT"], base["NOW"]
fixtures = base["fixtures"]
simulate_no_effect = base["simulate_no_effect"]
receipt_digest_valid = base["receipt_digest_valid"]


def rehash(receipt):
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    receipt["receipt_sha256"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        .encode("ascii")
    ).hexdigest()
    return receipt


class ReceiptAuthorityBoundary(unittest.TestCase):
    def setUp(self):
        docs = fixtures()

        async def get(component, path):
            return deepcopy(docs[component])

        self.receipt = asyncio.run(simulate_no_effect(INTENT, get=get, now=NOW))
        self.assertTrue(receipt_digest_valid(self.receipt))

    def test_mutation_without_rehash_is_rejected(self):
        for field, value in (
            ("run_id", "RUN-FOREIGN-001"),
            ("incident_id", "INC-FOREIGN-001"),
            ("core_request_sha256", "b" * 64),
            ("twin_approval_nonce_sha256", "c" * 64),
        ):
            with self.subTest(field=field):
                changed = deepcopy(self.receipt)
                changed[field] = value
                self.assertFalse(receipt_digest_valid(changed))

    def test_rehashed_privilege_escalation_remains_rejected(self):
        for field, value in (
            ("human_approved", True),
            ("execution_allowed", True),
            ("effect_allowed", True),
            ("glpi_write", True),
            ("resolution_verified", True),
            ("receipt_status", "RESOLVED"),
            ("receipt_phase", "POST_RESOLUTION"),
            ("effect_receipts", 1),
        ):
            with self.subTest(field=field):
                changed = rehash(dict(self.receipt, **{field: value}))
                self.assertFalse(receipt_digest_valid(changed))

    def test_valid_rehashed_foreign_run_is_not_authority(self):
        # Intentionally demonstrate the checksum boundary: an attacker can
        # recompute an unkeyed digest for a different Run/Incident. Consumers
        # MUST compare identity against authenticated Core/Temporal state.
        changed = rehash(dict(self.receipt, run_id="RUN-FOREIGN-001"))
        self.assertTrue(receipt_digest_valid(changed))
        self.assertNotEqual(changed["run_id"], INTENT["run_id"])
        self.assertNotEqual(changed["receipt_sha256"], self.receipt["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
