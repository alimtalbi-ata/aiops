"""Contract boundary guard for INT10 C/B: incompatible terminal wires stay unbridged."""
import ast
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
class TerminalContractBoundary(unittest.TestCase):
    def test_int09_terminal_helper_is_not_claimed_as_b_terminal_reject(self):
        path = ROOT / "app/worker/hitl_reject_terminal_runtime.py"
        tree = ast.parse(path.read_text())
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "recover_terminal_once")
        args = [a.arg for a in fn.args.args]
        kw = [a.arg for a in fn.args.kwonlyargs]
        self.assertEqual(args, ["args"])
        self.assertEqual(kw, ["owner", "post"])
        validate = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "validate_request")
        source = ast.get_source_segment(path.read_text(), validate)
        self.assertIn("incident_id", source)
        self.assertIn("event_id", source)
        self.assertIn("proposal_revision", source)
        # Explicitly guard the mismatch; this is NOT the B eight-field wire.
        self.assertNotIn("terminal_reject", source)
    def test_b_terminal_contract_is_not_silently_imported_or_invoked(self):
        worker = ROOT / "app/worker"
        for path in worker.glob("*.py"):
            if path.name == "hitl_reject_terminal_runtime.py":
                continue
            source = path.read_text()
            with self.subTest(path=path.name):
                self.assertNotIn("recover_terminal_once(", source)
