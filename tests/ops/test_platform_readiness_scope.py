"""Regression: platform smoke PASS must never imply a live E2E/deployment PASS."""
import ast
from pathlib import Path
import unittest

GATE = Path(__file__).resolve().parents[2] / "scripts/ops/platform_readiness_gate.py"

class PlatformReadinessScopeTests(unittest.TestCase):
    def test_report_has_explicit_unverified_gates(self):
        tree = ast.parse(GATE.read_text(encoding="utf-8"))
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        report_assign = next(n for n in ast.walk(main)
                             if isinstance(n, ast.Assign)
                             and any(isinstance(t, ast.Name) and t.id == "report" for t in n.targets))
        fields = {key.value: value.value for key, value in zip(report_assign.value.keys, report_assign.value.values)
                  if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)}
        self.assertEqual(fields["qualification_scope"], "read_only_platform_smoke")
        self.assertEqual(fields["e2e_verdict"], "NOT_VERIFIED")
        self.assertEqual(fields["deployment_verdict"], "NOT_VERIFIED")

if __name__ == "__main__":
    unittest.main()
