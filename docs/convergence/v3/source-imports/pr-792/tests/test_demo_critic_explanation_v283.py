"""Offline tests for ACME Demo Studio evidence-backed explanation."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("demo_explain", ROOT / "app/portal/demo_explain.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class DemoExplanationTests(unittest.TestCase):
    def test_blocked_critic_exposes_grounding_and_no_policy(self):
        ledger = {"analyses": [{"output": {"severity": "UNKNOWN"}}],
                  "critiques": [{"model": "mistral", "validated": False, "output": {
                      "final_recommendation": "HUMAN_APPROVAL",
                      "claim_checks": [{"claim": "FC failures observed", "supported": True,
                                        "supporting_evidence_ids": ["E1"]},
                                       {"claim": "Fabric is root cause", "supported": False}],
                      "issues": [{"code": "CAUSAL_LEAP", "description": "Insufficient proof",
                                  "evidence_ids": ["E1"]}],
                      "unsafe_actions": ["manual failover"]
                  }}], "policy_decisions": []}
        html = module.render_critic_explanation(ledger)
        for expected in ["HUMAN_APPROVAL", "UNKNOWN", "1/2", "CAUSAL_LEAP",
                         "E1", "aucune décision Policy", "Actions contestées"]:
            self.assertIn(expected, html)

    def test_escapes_model_content_and_missing_critique(self):
        html = module.render_critic_explanation({"critiques": [{"model": "<script>", "output": {
            "issues": [{"code": "<x>", "description": "<img src=x onerror=alert(1)>"}]}}]})
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Aucune critique", module.render_critic_explanation({}))


if __name__ == "__main__":
    unittest.main()
