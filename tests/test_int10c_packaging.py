"""Offline packaging boundary checks: historical bodies stay unregistered."""
import ast
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "worker"
class PackagingBoundary(unittest.TestCase):
    def test_historical_activity_body_has_no_temporal_registration(self):
        tree = ast.parse((APP / "int10c_activity_body.py").read_text())
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                self.assertFalse(any(a.name.startswith("temporalio") for a in n.names))
            if isinstance(n, ast.ImportFrom):
                self.assertFalse((n.module or "").startswith("temporalio"))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
                self.assertNotIn(n.func.id, {"activity", "defn"})
    def test_recovery_helpers_are_not_registered_or_imported_by_worker(self):
        forbidden = ("recover_terminal_once", "deliver_core_reject_once", "acme_simulated_no_effect")
        for path in APP.glob("*.py"):
            if path.name in {"int10c_activity_body.py", "hitl_reject_terminal_runtime.py", "hitl_reject_core_wire.py"}:
                continue
            for symbol in forbidden:
                with self.subTest(path=path.name, symbol=symbol):
                    self.assertNotIn(symbol, path.read_text())
    def test_terminal_recovery_is_injected_and_has_no_transport_dependency(self):
        tree = ast.parse((APP / "hitl_reject_terminal_runtime.py").read_text())
        modules = []
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                modules.extend(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                modules.append(n.module or "")
        self.assertFalse(any(x.startswith(("requests", "httpx", "temporalio", "psycopg")) for x in modules))
        fn = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "recover_terminal_once")
        self.assertEqual([a.arg for a in fn.args.args], ["args"])
        self.assertEqual([a.arg for a in fn.args.kwonlyargs], ["owner", "post"])
