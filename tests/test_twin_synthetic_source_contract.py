"""Source-only regression fence for the existing Twin synthetic endpoint.

This is NOT an OIDC, host, HMAC or end-to-end acceptance test.
Run: python3 -m unittest discover -s tests -p 'test_twin_synthetic_source_contract.py'
"""
import ast
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "app/twin/main.py"


class TwinSyntheticSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        cls.functions = {n.name: n for n in ast.walk(cls.tree)
                         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}

    def test_synthetic_route_remains_post_only(self):
        fn = self.functions["synthetic_event"]
        routes = [d for d in fn.decorator_list if isinstance(d, ast.Call)
                  and isinstance(d.func, ast.Attribute)]
        self.assertTrue(any(d.func.attr == "post"
                            and d.args and isinstance(d.args[0], ast.Constant)
                            and d.args[0].value == "/api/twin/synthetic-event"
                            for d in routes))

    def test_token_and_run_id_guards_precede_db_access(self):
        fn = self.functions["synthetic_event"]
        guards = [n for n in fn.body if isinstance(n, ast.If)]
        self.assertGreaterEqual(len(guards), 2)
        self.assertIn("authorization", ast.unparse(guards[0].test))
        self.assertIn("SIM_TOKEN", ast.unparse(guards[0].test))
        self.assertIn("401", ast.unparse(guards[0]))
        self.assertIn("run_id", ast.unparse(guards[1].test))
        self.assertIn("422", ast.unparse(guards[1]))
        first_db = next(i for i, n in enumerate(fn.body)
                        if isinstance(n, ast.With))
        self.assertLess(fn.body.index(guards[0]), first_db)
        self.assertLess(fn.body.index(guards[1]), first_db)

    def test_invalid_actions_and_missing_target_fail_before_db(self):
        fn = self.functions["synthetic_event"]
        guards = [n for n in fn.body if isinstance(n, ast.If)]
        self.assertGreaterEqual(len(guards), 4)
        self.assertIn("SET_STATE", ast.unparse(guards[2].test))
        self.assertIn("OBSERVE", ast.unparse(guards[2].test))
        self.assertIn("422", ast.unparse(guards[2]))
        self.assertIn("target_node_id", ast.unparse(guards[3].test))
        self.assertIn("422", ast.unparse(guards[3]))
        first_db = next(i for i, n in enumerate(fn.body)
                        if isinstance(n, ast.With))
        self.assertLess(fn.body.index(guards[2]), first_db)
        self.assertLess(fn.body.index(guards[3]), first_db)

    def test_response_echoes_run_id_for_cross_view_correlation(self):
        fn = self.functions["synthetic_event"]
        returns = [n for n in fn.body if isinstance(n, ast.Return)]
        self.assertEqual(len(returns), 1)
        response = returns[0].value
        self.assertIsInstance(response, ast.Dict)
        keys = [k.value if isinstance(k, ast.Constant) else None for k in response.keys]
        self.assertIn("run_id", keys)
        self.assertEqual(ast.unparse(response.values[keys.index("run_id")]), "x.run_id")

    def test_no_human_approval_claim_in_synthetic_response(self):
        fn = self.functions["synthetic_event"]
        returns = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
        self.assertTrue(returns)
        for ret in returns:
            keys = [k.value for k in ret.value.keys if isinstance(k, ast.Constant)] if isinstance(ret.value, ast.Dict) else []
            self.assertNotIn("human_approved", keys)
            self.assertNotIn("oidc_verified", keys)
        self.assertIn("'synthetic': True", ast.unparse(fn))


if __name__ == "__main__":
    unittest.main()
