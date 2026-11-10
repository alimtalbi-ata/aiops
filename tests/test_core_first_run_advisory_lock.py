"""Core first-run idempotency: absent rows require a transaction-scoped key lock."""
import ast
import json
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Cursor:
    def __init__(self, existing=None):
        self.existing = existing
        self.calls = []
        self.last = None

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.last = sql
        return self

    def fetchone(self):
        if "from aiops.runs where idempotency_key" in self.last:
            return self.existing
        return None


class FirstRunLockTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create")
        fn.decorator_list = []
        cls.code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, existing=None, mode="DEMO", incident_id="INC-147", key="fs147-run-key"):
        cursor = Cursor(existing)

        @contextmanager
        def db():
            yield cursor

        scope = {
            "db": db, "auth": lambda token: None, "bearer": lambda token: token,
            "HTTPException": HTTPException, "new": lambda prefix: prefix + "-NEW",
            "STAGES": [], "append_event": lambda *a, **k: None,
        }
        exec(self.code, scope)
        request = SimpleNamespace(mode=mode, scenario_id="FS147",
                                  incident_id=incident_id, idempotency_key=key)
        try:
            result = scope["create"](request, authorization="token")
        except HTTPException as exc:
            result = exc
        return result, cursor.calls

    def test_lock_precedes_lookup_of_absent_row(self):
        result, calls = self.invoke()
        self.assertEqual(result["run_id"], "RUN-NEW")
        self.assertIn("pg_advisory_xact_lock", calls[0][0])
        self.assertIn("hashtextextended", calls[0][0])
        self.assertEqual(calls[0][1], ("core:run-idempotency:fs147-run-key",))
        self.assertIn("from aiops.runs where idempotency_key", calls[1][0])
        self.assertEqual(sum("insert into aiops.runs" in sql for sql, _ in calls), 1)

    def test_same_key_same_intent_reuses_existing_run(self):
        existing = ("RUN-ORIGINAL", "DEMO", "FS147", "CREATED", 1, "INC-147")
        result, calls = self.invoke(existing)
        self.assertEqual(result["run_id"], "RUN-ORIGINAL")
        self.assertEqual(len(calls), 2)

    def test_same_key_different_intent_rejected_without_insert(self):
        existing = ("RUN-ORIGINAL", "DEMO", "FS147", "CREATED", 1, "INC-147")
        for mode, incident in (("LIVE", "INC-147"), ("DEMO", "INC-OTHER")):
            with self.subTest(mode=mode, incident=incident):
                result, calls = self.invoke(existing, mode=mode, incident_id=incident)
                self.assertIsInstance(result, HTTPException)
                self.assertEqual(result.status_code, 409)
                self.assertFalse(any("insert into aiops.runs" in sql for sql, _ in calls))

    def test_lock_key_is_scoped_to_full_idempotency_key(self):
        _, a = self.invoke(key="first")
        _, b = self.invoke(key="second")
        self.assertNotEqual(a[0][1], b[0][1])


if __name__ == "__main__":
    unittest.main()
