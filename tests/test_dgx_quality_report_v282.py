"""Synthetic, offline verification of bounded DGX quality report projection."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("dgx_report", ROOT / "tools/qualify_dgx_contract_v281.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class QualityReportTests(unittest.TestCase):
    def test_issues_and_hypothesis_links_preserved_without_unknown_ids(self):
        analysis = {"hypotheses": [{"id": "H1", "confidence": .7,
                    "supporting_evidence_ids": ["E-SAN-PORT", "E-FORGED"],
                    "assumptions": ["unverified cable"]}]}
        critique = {"issues": [{"code": "UNSAFE_ACTION", "description": "Require approval",
                     "evidence_ids": ["E-SAN-PATHS", "E-FORGED"]}],
                    "claim_checks": [{"supported": False, "supporting_evidence_ids": []}],
                    "unsafe_actions": ["manual failover"]}
        result = module.summarize_quality(analysis, critique)
        self.assertEqual(result["hypotheses"][0]["supporting_evidence_ids"], ["E-SAN-PORT"])
        self.assertEqual(result["hypotheses"][0]["assumptions_count"], 1)
        self.assertEqual(result["critic_objections"][0]["evidence_ids"], ["E-SAN-PATHS"])
        self.assertFalse(result["claim_checks"][0]["supported"])
        self.assertEqual(result["unsafe_actions_count"], 1)
        self.assertTrue(result["analyst_confidence_is_model_asserted_not_calibrated"])

    def test_bounded_details(self):
        issues = [{"code": "CONTRADICTION", "description": "x" * 1000} for _ in range(45)]
        result = module.summarize_quality({}, {"issues": issues})
        self.assertEqual(len(result["critic_objections"]), 30)
        self.assertEqual(len(result["critic_objections"][0]["description"]), 350)


if __name__ == "__main__":
    unittest.main()
