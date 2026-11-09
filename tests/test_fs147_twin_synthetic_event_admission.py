"""Twin synthetic-event admission regression (offline; no database or Docker).

Executes the actual route function AST with a fake DB to avoid importing
production configuration/secrets or opening network connections.
"""
import ast
from pathlib import Path
import types
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Event:
    def __init__(self, action, target_node_id=None, run_id="RUN-FIXTURE", payload=None):
        self.action, self.target_node_id, self.run_id = action, target_node_id, run_id
        self.payload = payload or {}


class DB:
    def __init__(self, node_exists=True):
        self.calls = 0
        self.statements = []
        self.node_exists = node_exists

    def __call__(self):
        self.calls += 1
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, query, params):
        self.statements.append((query, params))
        return self

    def fetchone(self):
        return (1,) if self.node_exists else None


def load_route(fake_db):
    path = Path(__file__).resolve().parents[1] / "app" / "twin" / "main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "synthetic_event")
    route.decorator_list = []
    namespace = {"HTTPException": HTTPException, "SyntheticEvent": Event,
                 "Header": lambda default=None: default, "SIM_TOKEN": "fixture-secret",
                 "db": fake_db, "new": lambda prefix: prefix + "-FIXTURE"}
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["synthetic_event"]


class SyntheticEventAdmission(unittest.TestCase):
    def test_unknown_action_fails_closed_without_database_access(self):
        db = DB()
        route = load_route(db)
        for action in ("NOOP", "DELETE", "", "OBSERVE "):
            with self.subTest(action=action), self.assertRaises(HTTPException) as caught:
                route(Event(action, "SAN-ARRAY"), authorization="Bearer fixture-secret")
            self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(db.calls, 0)

    def test_supported_actions_require_target_before_database_access(self):
        db = DB()
        route = load_route(db)
        for action in ("OBSERVE", "SET_STATE"):
            with self.subTest(action=action), self.assertRaises(HTTPException) as caught:
                route(Event(action), authorization="Bearer fixture-secret")
            self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(db.calls, 0)

    def test_ambiguous_run_and_target_ids_fail_before_database_access(self):
        for run_id in ("", " ", " RUN-FIXTURE", "RUN-FIXTURE ", "RUN\\nFS", "RUN\\x7fFS"):
            with self.subTest(run_id=repr(run_id)):
                db = DB()
                with self.assertRaises(HTTPException) as caught:
                    load_route(db)(Event("OBSERVE", "FS-FIXTURE-NODE", run_id=run_id,
                                         payload={"metric": "fs_used", "value": 91}),
                                   authorization="Bearer fixture-secret")
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(db.calls, 0)
        for node in ("", " ", " SAN-ARRAY", "FS-FIXTURE-NODE ", "FS\\nSAN", "FS\\x7fSAN"):
            with self.subTest(node=repr(node)):
                db = DB()
                with self.assertRaises(HTTPException) as caught:
                    load_route(db)(Event("SET_STATE", node, payload={"state": "DEGRADED"}),
                                   authorization="Bearer fixture-secret")
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(db.calls, 0)

    def test_valid_observation_retains_existing_contract(self):
        db = DB()
        result = load_route(db)(Event("OBSERVE", "FS-FIXTURE-NODE",
                                      payload={"metric": "fs_used", "value": 91}),
                                authorization="Bearer fixture-secret")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(db.calls, 1)
        self.assertEqual(len(db.statements), 2)
        self.assertIn("select 1 from aiops.twin_nodes", db.statements[0][0])
        self.assertIn("insert into aiops.observations", db.statements[1][0])

    def test_missing_target_never_writes_or_claims_pass(self):
        for action in ('OBSERVE', 'SET_STATE'):
            with self.subTest(action=action):
                db = DB(node_exists=False)
                with self.assertRaises(HTTPException) as caught:
                    load_route(db)(Event(action, 'SAN-NOT-IN-TOPOLOGY'), authorization='Bearer fixture-secret')
                self.assertEqual(caught.exception.status_code, 404)
                self.assertEqual(db.calls, 1)
                self.assertEqual(len(db.statements), 1)
                self.assertTrue(db.statements[0][0].startswith('select 1'))

    def test_observation_rejects_nonfinite_or_nonnumeric_value_without_db(self):
        import math
        for value in (True, False, "91", [], {}, float("nan"), float("inf"), -float("inf"), 10 ** 1000):
            with self.subTest(value=repr(value)):
                db = DB()
                with self.assertRaises(HTTPException) as caught:
                    load_route(db)(Event("OBSERVE", "FS-FIXTURE-NODE",
                                         payload={"metric": "fs_used", "value": value}),
                                   authorization="Bearer fixture-secret")
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(db.calls, 0)

    def test_missing_observation_evidence_fails_before_db(self):
        for payload in ({}, {"metric": "fs_used"}, {"metric": "", "value": 91},
                        {"metric": "  ", "value": 91},
                        {"metric": 147, "value": 91},
                        {"metric": "fs_used", "value": None}):
            with self.subTest(payload=payload):
                db = DB()
                with self.assertRaises(HTTPException) as caught:
                    load_route(db)(Event("OBSERVE", "FS-FIXTURE-NODE", payload=payload),
                                   authorization="Bearer fixture-secret")
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(db.calls, 0)

    def test_missing_state_fails_before_db(self):
        for payload in ({}, {"state": ""}, {"state": " "},
                        {"state": None}, {"state": 1}):
            with self.subTest(payload=payload):
                db = DB()
                with self.assertRaises(HTTPException) as caught:
                    load_route(db)(Event("SET_STATE", "SAN-FIXTURE-NODE", payload=payload),
                                   authorization="Bearer fixture-secret")
                self.assertEqual(caught.exception.status_code, 422)
                self.assertEqual(db.calls, 0)

    def test_valid_state_retains_write_path(self):
        db = DB()
        result = load_route(db)(Event("SET_STATE", "SAN-FIXTURE-NODE",
                                      payload={"state": "DEGRADED", "health": "WARN"}),
                                authorization="Bearer fixture-secret")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(len(db.statements), 3)
        self.assertIn("update aiops.twin_nodes", db.statements[1][0])
        self.assertIn("insert into aiops.twin_facts", db.statements[2][0])

    def test_invalid_token_does_not_open_database(self):
        db = DB()
        with self.assertRaises(HTTPException) as caught:
            load_route(db)(Event("OBSERVE", "FS-FIXTURE-NODE"), authorization="Bearer wrong")
        self.assertEqual(caught.exception.status_code, 401)
        self.assertEqual(db.calls, 0)


if __name__ == "__main__":
    unittest.main()
