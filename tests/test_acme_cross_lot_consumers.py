"""Cross-lot consumer contract tests: Portal A payload and Worker C boundary.

All Portal inputs are local STORY_OFFLINE fixtures. Worker intent is tested
only as a rejection boundary; this does not invoke Temporal or any service.
"""
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from portal.acme_impact_read_model import build_acme_impact_read_model
from portal.acme_incident_cockpit import project_synthetic_incident_cockpit
from importlib.util import find_spec

# C is delivered on a separate branch until convergence. Never mask errors
# importing a Worker module once it is present.
HAS_WORKER = find_spec('worker.acme_simulated_hitl') is not None
if HAS_WORKER:
    from worker.acme_simulated_hitl import (
        ISSUER, SandboxDenied, validate_intent, verify_no_effect_receipt,
    )


class CrossLotConsumerContractTests(unittest.TestCase):
    def setUp(self):
        self.impact = build_acme_impact_read_model()
        self.twin = self.impact["twin_evidence"]

    def test_frontend_payload_contract_is_complete_and_single_snapshot(self):
        cockpit = project_synthetic_incident_cockpit(self.impact)
        self.assertEqual(cockpit["source_sha256"], self.impact["source_sha256"])
        self.assertEqual(cockpit["twin_consumer"], self.impact["twin_consumer"])
        self.assertEqual(cockpit["signal_context"], self.impact["signal_context"])
        signal = cockpit["signal_context"]
        self.assertEqual(signal["source_sha256"], cockpit["source_sha256"])
        self.assertEqual(signal["incident_id"], cockpit["incident_id"])
        self.assertEqual(signal["impact_incident_id"], cockpit["business_impact_incident_id"])
        self.assertEqual(signal["scope"], "STORY_OFFLINE")
        self.assertFalse(signal["runtime_attested"])
        self.assertTrue(all(x["runtime_freshness"] == "UNKNOWN" for x in signal["signals"]))
        self.assertEqual(cockpit["twin_consumer"]["freshness"]["status"], "UNKNOWN")
        self.assertIsNone(cockpit["twin_consumer"]["binding"]["tenant_id"])
        self.assertIsNone(cockpit["twin_consumer"]["binding"]["attempt_id"])

    def test_frontend_projection_rejects_mixed_snapshot(self):
        import copy
        mixed = copy.deepcopy(self.impact)
        mixed["signal_context"]["source_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            project_synthetic_incident_cockpit(mixed)

    @unittest.skipUnless(HAS_WORKER, 'Requires lot C module at convergence')
    def test_worker_accepts_only_its_separate_runtime_sandbox_identity_shape(self):
        valid = {
            "attempt_id": "ACME-SIM-TEST-001", "tenant_id": "ACME-TEST",
            "scenario_id": "ACME-SAN-PAYMENTS", "mode": "SIMULATION",
            "approval_issuer": ISSUER, "incident_id": "INC-TEST-001",
            "run_id": "RUN-TEST-001", "proposal_id": "PROP-TEST-001",
            "approval_id": "SIM-APP-TEST-001", "ticket_id": "SIM-GLPI-TEST-001",
            "idempotency_key": "ACME-SIM-TEST-001", "human_approved": False,
            "execution_allowed": False, "effect_allowed": False,
        }
        self.assertEqual(validate_intent(valid), valid)
        story_bound = dict(valid, attempt_id=self.twin["run_id"],
                           idempotency_key=self.twin["run_id"],
                           tenant_id=self.twin["tenant_id"])
        with self.assertRaises(SandboxDenied):
            validate_intent(story_bound)

    @unittest.skipUnless(HAS_WORKER, 'Requires lot C module at convergence')
    def test_story_twin_cannot_be_replayed_as_worker_receipt(self):
        expected = {
            "attempt_id": "ACME-SIM-TEST-001", "tenant_id": "ACME-TEST",
            "incident_id": "INC-TEST-001", "run_id": "RUN-TEST-001",
            "proposal_id": "PROP-TEST-001", "ticket_id": "SIM-GLPI-TEST-001",
            "approval_id": "SIM-APP-TEST-001",
        }
        self.assertFalse(verify_no_effect_receipt(self.twin, expected))

    def test_identity_namespaces_do_not_alias(self):
        story = self.impact["twin_evidence"]
        signal = self.impact["signal_context"]
        self.assertEqual(story["run_id"], signal["run_id"])
        self.assertTrue(story["run_id"].startswith("SIM-ACME-"))
        self.assertFalse(story["run_id"].startswith("ACME-SIM-"))
        self.assertIsNone(story["tenant_id"])
        self.assertIsNone(story["attempt_id"])
        self.assertIsNone(story["resource_id"])
        self.assertIsNone(story["service_id"])


if __name__ == "__main__":
    unittest.main()
