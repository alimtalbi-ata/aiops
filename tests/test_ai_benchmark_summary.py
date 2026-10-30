import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from summarize_ai_benchmark import aggregate_reports


def report(model="qwen3:4b", dataset="abc", total=20, complete=True, result="PASS"):
    return {
        "evaluation_id": "EVAL-" + str(total) + model,
        "dataset_sha256": dataset,
        "provider": "ollama",
        "model": model,
        "prompt_version": "analyst-v2.2+critic-v2.4",
        "mode": "DEMO",
        "execution_allowed": False,
        "qualification_kind": "configured-model-evaluation",
        "result": result,
        "metrics": {
            "severity_accuracy": 0.8,
            "grounding": 1.0,
            "freshness_accuracy": 1.0,
            "action_safety": 1.0,
            "injection_resistance": 1.0,
            "contradiction_detection": 1.0,
            "stale_detection": 1.0,
            "critic_disposition": 0.8,
            "proposal_actionability": 0.75,
            "action_target_accuracy": 1.0,
            "action_type_validity": 1.0,
            "action_evidence_grounding": 1.0,
            "precondition_completeness": 1.0,
            "postcondition_testability": 1.0,
            "rollback_completeness": 1.0,
            "latency_ms_p50": 120.0,
            "latency_ms_p95": 300.0,
            "usage_coverage": 1.0 if complete else 0.0,
            "retry_count": 0,
            "token_totals_complete": complete,
            "total_tokens": total if complete else None,
            "prompt_tokens_total": total // 2 if complete else None,
            "completion_tokens_total": total // 2 if complete else None,
            "cost_usd": None,
            "cost_status": "UNKNOWN_PRICING_NOT_CONFIGURED",
            "cases_total": 5,
            "cases_analyzed": 5,
        },
    }


class BenchmarkSummaryTests(unittest.TestCase):
    def write(self, directory, name, value):
        path = pathlib.Path(directory) / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_aggregates_repeats_without_inventing_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                self.write(directory, "qwen3-4b-repeat-1.json", report(total=20)),
                self.write(directory, "qwen3-4b-repeat-2.json", report(total=30)),
                self.write(directory, "qwen3-4b-repeat-3.json", report(total=40)),
            ]
            result = aggregate_reports(paths)
            model = result["model_results"][0]
            self.assertEqual(model["repeats"], 3)
            self.assertEqual(model["evaluation_passes"], 3)
            self.assertEqual(model["total_tokens_mean"], 30)
            self.assertIsNone(model["cost_usd_mean"])
            self.assertEqual(model["cost_status"], "UNKNOWN_OR_PARTIAL")
            self.assertFalse(result["execution_allowed"])

    def test_refuses_mixed_dataset_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                self.write(directory, "a-repeat-1.json", report(dataset="abc")),
                self.write(directory, "b-repeat-1.json", report(model="qwen3:8b", dataset="different")),
            ]
            with self.assertRaisesRegex(ValueError, "dataset SHA-256 differs"):
                aggregate_reports(paths)

    def test_refuses_live_or_execution_enabled_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            value = report()
            value["execution_allowed"] = True
            path = self.write(directory, "live-repeat-1.json", value)
            with self.assertRaisesRegex(ValueError, "execution authority"):
                aggregate_reports([path])

    def test_incomplete_provider_usage_stays_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [
                self.write(directory, "qwen3-4b-repeat-1.json", report(complete=False)),
                self.write(directory, "qwen3-4b-repeat-2.json", report(complete=False)),
            ]
            model = aggregate_reports(paths)["model_results"][0]
            self.assertIsNone(model["total_tokens_mean"])
            self.assertEqual(model["usage_complete_repeats"], 0)
            self.assertIsNone(model["usage_coverage_mean"])

    def test_ollama_cpu_workflow_fails_closed_and_uses_bounded_baseline(self):
        workflow = (ROOT / ".github" / "workflows" / "ollama-ai-benchmark.yml").read_text(encoding="utf-8")
        compose = (ROOT / ".github" / "compose.ollama-benchmark.yml").read_text(encoding="utf-8")
        self.assertIn('model: ["qwen3:1.7b", "qwen3:4b"]', workflow)
        self.assertIn('AIOPS_BENCHMARK_TIMEOUT_SECONDS: "300"', workflow)
        self.assertIn('AIOPS_EVALUATOR_TIMEOUT_SECONDS: "330"', workflow)
        self.assertIn('AIOPS_BENCHMARK_MAX_OUTPUT_TOKENS: "2048"', workflow)
        self.assertIn('default: "1"', workflow)
        self.assertIn("Fail benchmark job when any evaluator repeat fails", workflow)
        self.assertIn("grep -Ev", workflow)
        self.assertIn("evaluator_exit=0", workflow)
        self.assertIn("AIOPS_LLM_MAX_OUTPUT_TOKENS:", compose)
        self.assertIn("AIOPS_LLM_MAX_REQUEST_BYTES:", compose)

    def test_prompt_version_must_match_for_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            first = report()
            second = report()
            second["prompt_version"] = "different"
            paths = [
                self.write(directory, "a-repeat-1.json", first),
                self.write(directory, "a-repeat-2.json", second),
            ]
            with self.assertRaisesRegex(ValueError, "prompt versions differ"):
                aggregate_reports(paths)


if __name__ == "__main__":
    unittest.main()
