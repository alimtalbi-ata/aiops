import copy
import datetime as dt
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "scripts/acme_demo_readiness.py"
spec = importlib.util.spec_from_file_location("acme_demo_readiness", P)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
NOW = dt.datetime(2026, 11, 16, 17, 0, tzinfo=dt.timezone.utc)

def receipt():
    return {"schema": "aiops.debian-acme-sim-e2e.v1",
            "collected_at": "2026-11-16T16:55:00+00:00",
            "attempt_id": "ACME-SIM-0123456789ABCDEF",
            "tenant_id": "ACME-TEST", "scenario_id": "ACME-SAN-PAYMENTS",
            "mode": "SIMULATION", "status": "PASS",
            "reason": "SIMULATED_SANDBOX_ONLY",
            "approval_issuer": "TWIN_ACME_SIMULATED",
            "human_approval_claimed": False, "live_effects_allowed": False,
            "real_glpi_writes_allowed": False, "docker_mutations": 0,
            "stages": {k: "PASS" for k in m.REQUIRED_STAGES},
            "ids": {**{k: "SYNTHETIC-" + k for k in m.REQUIRED_IDS},
                    "ticket_id": "SIM-GLPI-TEST-001",
                    "approval_id": "SIM-APP-TEST-001"}}

class Readiness(unittest.TestCase):
    def test_pass_is_simulation_only(self):
        self.assertEqual(m.assess(receipt(), NOW)["verdict"], "GO_SIMULATION_ONLY")
        self.assertEqual(m.assess(receipt(), NOW)["live"], "NO_GO")

    def test_wrong_terminal_reason(self):
        r = receipt(); r["reason"] = "UNVERIFIED"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_real_ticket_identifier_refused(self):
        r = receipt(); r["ids"]["ticket_id"] = "GLPI-123"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_non_simulated_approval_identifier_refused(self):
        r = receipt(); r["ids"]["approval_id"] = "HUMAN-APP-123"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_missing_attempt_identifier(self):
        r = receipt(); del r["attempt_id"]
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_malformed_attempt_identifier(self):
        r = receipt(); r["attempt_id"] = "ACME-SIM-FAKE"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_missing_receipt(self):
        self.assertEqual(m.assess(None, NOW)["verdict"], "NO_GO")

    def test_no_live_claim(self):
        r = receipt(); r["live_effects_allowed"] = True
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_no_real_glpi(self):
        r = receipt(); r["real_glpi_writes_allowed"] = True
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_no_fake_human(self):
        r = receipt(); r["human_approval_claimed"] = True
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_no_host_mutation(self):
        r = receipt(); r["docker_mutations"] = 1
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_missing_twin_capability_blocks(self):
        r = receipt(); del r["stages"]["capability_twin"]
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_failed_worker_receipt_blocks(self):
        r = receipt(); r["stages"]["worker_no_effect"] = "FAIL"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_missing_stage(self):
        r = receipt(); r["stages"] = {}
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_missing_id(self):
        r = receipt(); del r["ids"]["ticket_id"]
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_stale(self):
        r = receipt(); r["collected_at"] = "2026-11-15T16:55:00+00:00"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_future(self):
        r = receipt(); r["collected_at"] = "2026-11-17T16:55:00+00:00"
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

    def test_no_pass_on_boolean_zero(self):
        r = receipt(); r["docker_mutations"] = False
        self.assertEqual(m.assess(r, NOW)["verdict"], "NO_GO")

if __name__ == "__main__":
    unittest.main()
