"""Regression: canonical at-time view must not expose FS147/SAN synthetic RUN facts.

Runs the actual route AST with an in-memory fake DB; no production imports,
credentials, containers, database or network access.
"""
import ast
import json
from pathlib import Path
import unittest


class FakeDB:
    def __init__(self, rows):
        self.rows = rows
    def __call__(self):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, *_):
        return self
    def fetchall(self):
        return self.rows


def route_at(rows):
    path = Path(__file__).resolve().parents[1] / "app/twin/main.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    route = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "at")
    route.decorator_list = []
    namespace = {"db": FakeDB(rows)}
    exec(compile(ast.Module(body=[route], type_ignores=[]), str(path), "exec"), namespace)
    return namespace["at"]


def fact(id_, node, value):
    return (id_, node, "state", value, "t0", None, "t0", 1.0)


class HistoricalNonContamination(unittest.TestCase):
    def test_synthetic_fs_and_san_runs_never_enter_canonical_history(self):
        fs = fact("FACT-FS", "FS-LAB-147", json.dumps(
            {"state": "FAILED", "run_id": "RUN-FS147", "synthetic": True}))
        san = fact("FACT-SAN", "SAN-ARRAY", json.dumps(
            {"state": "FAILED", "run_id": "RUN-SAN", "synthetic": True}))
        canonical = fact("FACT-REAL", "SAN-ARRAY", json.dumps(
            {"state": "OK", "source": "cmdb"}))
        legacy = fact("FACT-LEGACY", "FS-LAB-147", "UP")
        result = route_at([fs, san, canonical, legacy])("2026-11-09T00:00:00Z")
        self.assertEqual([x["fact_id"] for x in result["facts"]],
                         ["FACT-REAL", "FACT-LEGACY"])

    def test_synthetic_marker_must_be_explicit_boolean_true(self):
        rows = [fact("A", "FS", {"synthetic": True}),
                fact("B", "FS", {"synthetic": "true"}),
                fact("C", "FS", '{"synthetic":true}'),
                fact("D", "FS", "not-json")]
        result = route_at(rows)("t0")
        self.assertEqual([x["fact_id"] for x in result["facts"]], ["B", "D"])


if __name__ == "__main__":
    unittest.main()
