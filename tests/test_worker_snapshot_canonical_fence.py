"""Synthetic readback snapshot integrity across both authenticated rounds.

Regression for otherwise-valid metadata rotation and Python bool/int equality.
No durable replay, PG16, Temporal, human approval or LIVE claim.
"""
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


class SnapshotCanonicalFence(unittest.IsolatedAsyncioTestCase):
    async def test_unqualified_metadata_rotation_denied_without_receipt(self):
        for component in ("core", "twin", "policy"):
            with self.subTest(component=component):
                docs = fixtures()
                calls = []
                async def get(name, path):
                    self.assertTrue(path.endswith(INTENT["attempt_id"]))
                    calls.append(name)
                    document = deepcopy(docs[name])
                    if len(calls) > 3 and name == component:
                        document["synthetic_audit_revision"] = "rotated"
                    return document
                with self.assertRaises(SandboxDenied):
                    await simulate_no_effect(INTENT, get=get, now=NOW)
                self.assertEqual(calls, ["core", "twin", "policy"] * 2)

    async def test_boolean_to_integer_rotation_denied(self):
        docs = fixtures()
        calls = []
        async def get(name, path):
            calls.append(name)
            document = deepcopy(docs[name])
            document["synthetic_audit_flag"] = (
                1 if len(calls) > 3 and name == "policy" else True
            )
            return document
        with self.assertRaises(SandboxDenied):
            await simulate_no_effect(INTENT, get=get, now=NOW)
        self.assertEqual(calls, ["core", "twin", "policy"] * 2)

    async def test_reordered_json_object_keys_are_not_rotation(self):
        docs = fixtures()
        calls = []
        async def get(name, path):
            calls.append(name)
            document = deepcopy(docs[name])
            return dict(reversed(list(document.items()))) if len(calls) > 3 else document
        receipt = await simulate_no_effect(INTENT, get=get, now=NOW)
        self.assertEqual(calls, ["core", "twin", "policy"] * 2)
        self.assertTrue(receipt_digest_valid(receipt))
        self.assertEqual(receipt["receipt_status"], "SIMULATED_NO_EFFECT")
        self.assertEqual(receipt["receipt_phase"], "PRE_RESOLUTION")
        self.assertFalse(receipt["human_approved"])
        self.assertFalse(receipt["resolution_verified"])
        self.assertFalse(receipt["glpi_write"])
        self.assertEqual(receipt["effect_receipts"], 0)


if __name__ == "__main__":
    unittest.main()
