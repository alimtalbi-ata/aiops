"""Canonical historical Twin view must exclude synthetic provenance variants.

Offline execution of the actual /api/twin/at route with an isolated fake DB.
No host, PostgreSQL, container, or production mutation.
"""
import ast
import json
from pathlib import Path
import unittest


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
        self.statements = []

    def __call__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.statements.append((query, params))
        return self

    def fetchall(self):
        return self.rows


def load_at(fake_db):
    path = Path(__file__).resolve().parents[1] / "app/twin/main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    route = next(node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name == "at")
    route.decorator_list = []
    namespace = {"db": fake_db}
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["at"]


class CanonicalHistoryIsolation(unittest.TestCase):
    def test_fs147_and_san_synthetic_facts_never_leak_into_canonical_history(self):
        canonical = ("FACT-CANONICAL", "NODE-CANONICAL", "state",
                     {"state": "OK"}, None, None, None, 1.0)
        fs = ("FACT-FS147", "FS-LAB-147", "observation",
              json.dumps({"run_id": "RUN-FS147", "synthetic": True, "metric": "fs_used"}),
              None, None, None, 1.0)
        san = ("FACT-SAN", "SAN-ARRAY", "state",
               {"run_id": "RUN-SAN", "synthetic": "true", "state": "DEGRADED"},
               None, None, None, 1.0)
        legacy = ("FACT-SAN-LEGACY", "SAN-VOLUME", "observation",
                  json.dumps({"run_id": "RUN-SAN", "synthetic": "true"}),
                  None, None, None, 1.0)
        fake_db = FakeDB([canonical, fs, san, legacy])
        result = load_at(fake_db)("2026-11-09T20:00:00Z")
        self.assertEqual([fact["fact_id"] for fact in result["facts"]],
                         ["FACT-CANONICAL"])
        self.assertEqual(len(fake_db.statements), 1)
        self.assertIn("from aiops.twin_facts", fake_db.statements[0][0])
        self.assertFalse(any("insert " in sql.lower() or "update " in sql.lower()
                             for sql, _ in fake_db.statements))

    def test_string_false_is_not_treated_as_synthetic(self):
        row = ("FACT-CANONICAL", "NODE-CANONICAL", "state",
               json.dumps({"synthetic": "false", "state": "OK"}),
               None, None, None, 1.0)
        self.assertEqual(len(load_at(FakeDB([row]))("2026-11-09T20:00:00Z")["facts"]), 1)


if __name__ == "__main__":
    unittest.main()
