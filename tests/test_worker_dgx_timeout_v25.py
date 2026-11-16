"""Static guard for the Worker DGX timeout and Temporal budget."""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'app/worker/main.py'
WORKFLOW = ROOT / 'app/worker/workflow.py'

class WorkerDGXTimeoutTests(unittest.TestCase):
    def test_two_dgx_calls_use_bounded_timeout(self):
        tree = ast.parse(WORKER.read_text())
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == 'post_json'
                 and any(isinstance(arg, ast.Constant) and arg.value in (
                     '/api/intelligence/analyze', '/api/intelligence/critic')
                     for arg in node.args)]
        self.assertEqual(len(calls),2)
        for call in calls:
            timeout = next((kw.value for kw in call.keywords
                            if kw.arg == 'timeout'), None)
            self.assertIsInstance(timeout, ast.Name)
            self.assertEqual(timeout.id,'DGX_HTTP_TIMEOUT_SECONDS')

    def test_temporal_activity_has_budget(self):
        tree = ast.parse(WORKFLOW.read_text())
        self.assertIn('seconds=180', WORKFLOW.read_text())
        self.assertIn("between 15 and 150", WORKER.read_text())

if __name__=='__main__':
    unittest.main()
