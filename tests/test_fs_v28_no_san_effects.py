"""FS V28: executable AST guard against SAN side effects in the FS OBSERVE branch.

This source-only guard does not claim host execution or Evidence authenticity.
"""
import ast
from pathlib import Path
import unittest

WORKER = Path(__file__).resolve().parents[1] / "app/worker/main.py"


class FsV28NoSanEffects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(WORKER.read_text(encoding="utf-8"))
        execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                       and n.name == "_execute_stage_blocking")
        cls.branch = next(n for n in ast.walk(execute)
                          if isinstance(n, ast.If)
                          and "scenario == FS_V28_SCENARIO" in ast.unparse(n.test))
        cls.source = WORKER.read_text(encoding="utf-8")

    def test_fs_branch_has_only_evidence_read_and_validation(self):
        branch = self.branch.body
        calls = [n for statement in branch for n in ast.walk(statement)
                 if isinstance(n, ast.Call)]
        names = [n.func.id for n in calls if isinstance(n.func, ast.Name)]
        self.assertEqual(names.count("get_json"), 1)
        self.assertEqual(names.count("validate_fs_v28_observation"), 1)
        self.assertFalse({"post_json", "post", "put_json", "delete_json"} & set(names))
        self.assertIn("FS_V28_EVIDENCE_ID", ast.unparse(branch[0]))
        self.assertIn("rid", ast.unparse(branch[-1]))

    def test_legacy_san_writes_only_in_other_scenarios(self):
        # The SAN path must be the mutually exclusive elif, not an independent if.
        self.assertEqual(len(self.branch.orelse), 1)
        legacy = self.branch.orelse[0]
        self.assertIsInstance(legacy, ast.If)
        self.assertIn("stage == 'OBSERVE'", ast.unparse(legacy.test))
        legacy_calls = [n for n in ast.walk(legacy)
                        if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Name)
                        and n.func.id == "post_json"]
        self.assertGreaterEqual(len(legacy_calls), 2)
        self.assertIn("ACME-SAN-FABRIC-A", " ".join(ast.unparse(stmt) for stmt in legacy.body))


if __name__ == "__main__":
    unittest.main()
