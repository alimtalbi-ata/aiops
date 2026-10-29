import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "core": ["aiops_runs_total", "aiops_runs_running",
             "aiops_runs_blocked", "aiops_runs_resolved"],
    "twin": ["aiops_twin_nodes", "aiops_twin_degraded",
             "aiops_twin_failed"],
    "policy": ["aiops_policy_up"],
    "worker": ["aiops_worker_up"],
    "evidence": ["aiops_evidence_total"],
}

class PrometheusMetricsContractTest(unittest.TestCase):
    def test_metrics_routes(self):
        for service, metrics in EXPECTED.items():
            with self.subTest(service=service):
                path = ROOT / "app" / service / "main.py"
                source = path.read_text()
                tree = ast.parse(source)

                functions = [
                    node for node in tree.body
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and node.name == "metrics"
                ]

                self.assertEqual(len(functions), 1)

                function_source = ast.get_source_segment(
                    source, functions[0]
                )

                self.assertIn("PlainTextResponse", function_source)
                self.assertIn("text/plain; version=0.0.4", function_source)

                for metric in metrics:
                    self.assertIn(metric, function_source)

if __name__ == "__main__":
    unittest.main()
