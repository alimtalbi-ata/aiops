"""Offline regression: safe Policy denial is not an executed end-to-end use case."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("live_usecase_gate", ROOT / "scripts/ops/live_usecase_qualification.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

class LiveUsecaseBlockedGateTests(unittest.TestCase):
    def test_blocked_run_never_qualifies_full_e2e(self):
        linkage = {"checks": {"core_run": "PASS", "core_api": "PASS",
                    "evidence_api": "PASS", "critic_policy_outbox": "PASS",
                    "glpi_core_link": "PASS", "itsm_readback": "PASS"},
                   "database": {"run": {"status": "BLOCKED"}}}
        runtime = {"aiops2-rebuild-intelligence": {"state": "running"}}
        report = gate.summarize(linkage, {"verdict": "PASS", "runtime": runtime},
                                {}, "2026-11-09T05:00:00Z", {"status": "PASS"})
        self.assertEqual(report["verdict"], "HOLD")
        self.assertEqual(report["e2e_verdict"], "NOT_VERIFIED")
        self.assertEqual(report["blocking"], [])
        by_name = {c["name"]: c for c in report["checks"]}
        self.assertEqual(by_name["temporal_worker_history"]["status"], "NOT_APPLICABLE")
        self.assertEqual(by_name["hitl_action_binding"]["status"], "NOT_APPLICABLE")

    def test_missing_evidence_stays_hold(self):
        report = gate.summarize({}, {}, {}, "2026-11-09T05:00:00Z", {})
        self.assertEqual(report["verdict"], "HOLD")
        self.assertIn("core_run_consistency", report["blocking"])
        self.assertEqual(report["e2e_verdict"], "NOT_VERIFIED")

if __name__ == "__main__":
    unittest.main()
