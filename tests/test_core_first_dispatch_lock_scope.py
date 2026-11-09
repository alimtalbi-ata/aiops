"""Regression: first dispatch retains the PostgreSQL Run row lock until receipt readback.

This is a source-level contract check, not a substitute for PostgreSQL/Temporal E2E.
"""
import ast
import pathlib
import unittest


class FirstDispatchLockScopeTests(unittest.TestCase):
    def test_worker_dispatch_and_receipt_readback_are_inside_run_lock(self):
        source = pathlib.Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
        lock_scope = next(
            node for node in fn.body if isinstance(node, ast.With)
            and any(isinstance(item.context_expr, ast.Call)
                    and isinstance(item.context_expr.func, ast.Name)
                    and item.context_expr.func.id == "db"
                    for item in node.items)
        )
        sql = [
            n.value for n in ast.walk(lock_scope)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]
        self.assertTrue(any("for update" in q.lower() and "aiops.runs" in q.lower() for q in sql))
        self.assertTrue(any("insert into aiops.execution_receipts" in q.lower() for q in sql))
        self.assertTrue(any("select workflow_id from aiops.execution_receipts" in q.lower() for q in sql))
        worker_posts = [
            n for n in ast.walk(lock_scope) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute) and n.func.attr == "post"
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "requests"
        ]
        self.assertEqual(len(worker_posts), 1)
        self.assertFalse(any(
            isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "post" and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "requests"
            for stmt in fn.body if stmt is not lock_scope for n in ast.walk(stmt)
        ))


if __name__ == "__main__":
    unittest.main()
