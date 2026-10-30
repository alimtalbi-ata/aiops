import importlib.util
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aiops_eval_harness", ROOT / "tools" / "evaluate_ai_core.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

class AICoreEvaluationHarnessTests(unittest.TestCase):
    def test_analysis_reference_extraction_covers_all_material_sections(self):
        output = {
            "hypotheses": [{"supporting_evidence_ids": ["E1"], "contradicting_evidence_ids": ["E2"]}],
            "alternatives": [{"evidence_ids": ["E3"]}],
            "recommended_actions": [{"evidence_ids": ["E4"]}],
        }
        self.assertEqual(set(MODULE.refs_from_analysis(output)), {"E1", "E2", "E3", "E4"})

    def test_critic_reference_extraction_covers_issues_and_claim_checks(self):
        output = {
            "issues": [{"evidence_ids": ["E1"]}],
            "claim_checks": [{"supporting_evidence_ids": ["E2"], "contradicting_evidence_ids": ["E3"]}],
        }
        self.assertEqual(set(MODULE.refs_from_critique(output)), {"E1", "E2", "E3"})

    def test_invocation_aggregation_reports_provider_usage_and_latency(self):
        metrics = MODULE.aggregate_model_invocations([
            {"model_invocations": [
                {"usage_source": "provider_reported", "prompt_tokens": 10,
                 "completion_tokens": 5, "total_tokens": 15,
                 "latency_ms": 100, "retry_count": 0},
                {"usage_source": "provider_reported", "prompt_tokens": 20,
                 "completion_tokens": 10, "total_tokens": 30,
                 "latency_ms": 300, "retry_count": 1},
            ]}
        ])
        self.assertEqual(metrics["model_calls"], 2)
        self.assertEqual(metrics["usage_coverage"], 1.0)
        self.assertEqual(metrics["prompt_tokens_total"], 30)
        self.assertEqual(metrics["completion_tokens_total"], 15)
        self.assertEqual(metrics["total_tokens"], 45)
        self.assertEqual(metrics["latency_ms_p50"], 100)
        self.assertEqual(metrics["latency_ms_p95"], 300)
        self.assertEqual(metrics["retry_count"], 1)
        self.assertIsNone(metrics["cost_usd"])

    def test_partial_usage_never_claims_complete_token_totals_or_zero_cost(self):
        metrics = MODULE.aggregate_model_invocations([
            {"model_invocations": [
                {"usage_source": "provider_reported", "prompt_tokens": 10,
                 "completion_tokens": 5, "total_tokens": 15, "latency_ms": 100},
                {"usage_source": "unavailable", "prompt_tokens": None,
                 "completion_tokens": None, "total_tokens": None, "latency_ms": 200},
            ]}
        ])
        self.assertEqual(metrics["usage_coverage"], 0.5)
        self.assertIsNone(metrics["total_tokens"])
        self.assertEqual(metrics["reported_tokens_partial_sum"], 15)
        self.assertFalse(metrics["token_totals_complete"])
        self.assertEqual(metrics["cost_status"], "UNKNOWN_PRICING_NOT_CONFIGURED")

    def test_dataset_has_unique_ids_and_required_adversarial_cases(self):
        data = json.loads((ROOT / "eval" / "ai-core-cases.json").read_text(encoding="utf-8"))
        ids = [case["case_id"] for case in data["cases"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("prompt-injection-is-data", ids)
        self.assertIn("fresh-critical-conflicts-with-stale-healthy", ids)
        for case in data["cases"]:
            evidence_ids = [e["evidence_id"] for e in case["evidence"]]
            self.assertTrue(evidence_ids)
            self.assertEqual(len(evidence_ids), len(set(evidence_ids)))

if __name__ == "__main__":
    unittest.main()
