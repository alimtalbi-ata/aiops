"""Regression tests for the read-only live use-case release gate."""
import ast
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "ops" / "live_usecase_qualification.py"


class LiveUsecaseGateRegression(unittest.TestCase):
    def test_script_is_valid_python(self):
        ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))

    def test_blocked_policy_denial_never_promotes_e2e(self):
        spec = importlib.util.spec_from_file_location("live_usecase_gate", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        linkage = {
            "database": {"run": {"status": "BLOCKED"}},
            "checks": {
                "core_run": "PASS", "core_api": "PASS",
                "evidence_api": "PASS", "critic_policy_outbox": "PASS",
                "glpi_core_link": "PASS", "itsm_readback": "PASS",
            },
        }
        platform = {
            "verdict": "PASS",
            "runtime": {"aiops2-rebuild-intelligence": {"state": "running"}},
        }
        result = module.summarize(linkage, platform, {}, "2026-11-09T07:00:00+00:00",
                                  {"status": "PASS"})
        self.assertEqual(result["verdict"], "HOLD")
        self.assertEqual(result["e2e_verdict"], "NOT_VERIFIED")
        checks = {item["name"]: item for item in result["checks"]}
        self.assertEqual(checks["policy_denial_safety"]["status"], "PASS")
        self.assertEqual(checks["temporal_worker_history"]["status"], "NOT_APPLICABLE")
        self.assertEqual(checks["hitl_action_binding"]["status"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
