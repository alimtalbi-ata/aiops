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


    def test_both_synthetic_write_paths_preserve_run_id_in_payload(self):
        """Source fence only: persistence/cross-service correlation needs PG16 and host tests."""
        fn = self.functions["synthetic_event"]
        inserts = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == "execute"
                   and n.args and isinstance(n.args[0], ast.Constant)
                   and isinstance(n.args[0].value, str)
                   and "insert into aiops." in n.args[0].value.lower()]
        by_table = {}
        for call in inserts:
            sql = call.args[0].value.lower()
            for table in ("twin_facts", "observations"):
                if "insert into aiops." + table in sql:
                    by_table[table] = call
        self.assertEqual(set(by_table), {"twin_facts", "observations"})
        for table, call in by_table.items():
            payload = ast.unparse(call.args[1:])
            with self.subTest(table=table):
                self.assertIn("'run_id': x.run_id", payload)
                self.assertIn("'synthetic': True", payload)

    def test_synthetic_handler_does_not_start_temporal_or_claim_live_effect(self):
        fn = self.functions["synthetic_event"]
        body = ast.unparse(fn)
        for forbidden in ("start_workflow(", "execute_workflow(", "SIMULATED_NO_EFFECT = False",
                          "'human_approved': True", "'live': True"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, body)


    def test_synthetic_sql_uses_bound_parameters_not_interpolation(self):
        """Source fence: user-controlled action, node and payload must not form SQL text."""
        fn = self.functions["synthetic_event"]
        calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Attribute) and n.func.attr == "execute"]
        self.assertEqual(len(calls), 3)
        for call in calls:
            with self.subTest(sql=ast.unparse(call.args[0])[:90]):
                self.assertIsInstance(call.args[0], ast.Constant)
                self.assertIsInstance(call.args[0].value, str)
                self.assertGreaterEqual(len(call.args), 2)
                self.assertIsInstance(call.args[1], ast.Tuple)
                self.assertNotIn("{", call.args[0].value)
                self.assertNotIn("}", call.args[0].value)

    def test_synthetic_response_has_explicit_simulation_marker(self):
        fn = self.functions["synthetic_event"]
        returns = [n for n in fn.body if isinstance(n, ast.Return)]
        self.assertEqual(len(returns), 1)
        response = returns[0].value
        self.assertIsInstance(response, ast.Dict)
        values = {k.value: v for k, v in zip(response.keys, response.values)
                  if isinstance(k, ast.Constant)}
        self.assertIn("synthetic", values)
        self.assertIsInstance(values["synthetic"], ast.Constant)
        self.assertIs(values["synthetic"].value, True)
        self.assertNotIn("approved", values)
        self.assertNotIn("live", values)


if __name__ == "__main__":
    unittest.main()
