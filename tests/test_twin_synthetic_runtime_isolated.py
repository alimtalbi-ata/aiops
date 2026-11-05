"""Executable isolated Twin synthetic contract: no PG16, network, OIDC or LIVE effects."""
import ast
from pathlib import Path
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / "app/twin/main.py"


class Rejected(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Database:
    def __init__(self):
        self.calls = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, sql, params):
        self.calls.append((sql, params))


class SyntheticRuntimeContract(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "synthetic_event")
        fn.decorator_list = []
        fn.args.defaults = [ast.Constant(value=None)]
        module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))
        self.db = Database()
        scope = {"SIM_TOKEN": "isolated-test-token", "HTTPException": Rejected,
                 "db": lambda: self.db, "new": lambda kind: kind + "-test",
                 "SyntheticEvent": object}
        exec(compile(module, str(SOURCE), "exec"), scope)
        self.invoke = scope["synthetic_event"]

    def event(self, action="OBSERVE", node="ACME-TEST", run="RUN-TEST"):
        return type("Event", (), {"action": action, "target_node_id": node,
                                   "run_id": run, "payload": {"metric": "latency", "value": 2}})()

    def test_fail_closed_before_database_for_invalid_inputs(self):
        cases = [("bad token", self.event(), "Bearer invalid", 401),
                 ("missing run", self.event(run=None), "Bearer isolated-test-token", 422),
                 ("invalid action", self.event(action="LIVE"), "Bearer isolated-test-token", 422),
                 ("missing target", self.event(node=None), "Bearer isolated-test-token", 422)]
        for label, event, auth, status in cases:
            with self.subTest(label=label):
                with self.assertRaises(Rejected) as ctx:
                    self.invoke(event, auth)
                self.assertEqual(ctx.exception.status_code, status)
                self.assertEqual(self.db.calls, [])

    def test_observe_preserves_run_and_never_mutates_node(self):
        result = self.invoke(self.event(), "Bearer isolated-test-token")
        self.assertEqual((result["run_id"], result["synthetic"]), ("RUN-TEST", True))
        self.assertEqual(len(self.db.calls), 1)
        sql, params = self.db.calls[0]
        self.assertIn("insert into aiops.observations", sql.lower())
        self.assertIn('"run_id": "RUN-TEST"', params[-1])
        self.assertIn('"synthetic": true', params[-1])

    def test_set_state_records_synthetic_fact_with_same_run(self):
        result = self.invoke(self.event(action="SET_STATE"), "Bearer isolated-test-token")
        self.assertEqual(result["run_id"], "RUN-TEST")
        self.assertEqual(len(self.db.calls), 2)
        self.assertIn("update aiops.twin_nodes", self.db.calls[0][0].lower())
        self.assertIn("insert into aiops.twin_facts", self.db.calls[1][0].lower())
        self.assertIn('"run_id": "RUN-TEST"', self.db.calls[1][1][-1])
        self.assertIn('"synthetic": true', self.db.calls[1][1][-1])


    def test_distinct_runs_are_not_conflated_in_observation_payload(self):
        """Isolated contract only: does not prove Evidence joins or PG16 replay."""
        import json
        for run in ("RUN-ONE", "RUN-TWO"):
            result = self.invoke(self.event(run=run), "Bearer isolated-test-token")
            self.assertEqual(result["run_id"], run)
        self.assertEqual(len(self.db.calls), 2)
        payloads = [json.loads(params[-1]) for _, params in self.db.calls]
        self.assertEqual([p["run_id"] for p in payloads], ["RUN-ONE", "RUN-TWO"])
        self.assertTrue(all(p["synthetic"] is True for p in payloads))

    def test_database_error_never_returns_synthetic_pass(self):
        """A failed write must propagate; never manufacture PASS or approval."""
        class WriteFailure(RuntimeError):
            pass
        for action in ("OBSERVE", "SET_STATE"):
            with self.subTest(action=action):
                self.db.calls.clear()
                original_execute = self.db.execute
                def fail(sql, params):
                    original_execute(sql, params)
                    raise WriteFailure("isolated write failure")
                self.db.execute = fail
                with self.assertRaises(WriteFailure):
                    self.invoke(self.event(action=action), "Bearer isolated-test-token")
                self.db.execute = original_execute

if __name__ == "__main__":
    unittest.main()
