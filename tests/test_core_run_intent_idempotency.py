"""Functional regression for Core Run idempotency intent binding (no database/network)."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        if not query.lower().startswith("select "):
            raise AssertionError("Existing idempotency key must never write")
        return self

    def fetchone(self):
        return self.row


class RunIntentIdempotencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create")
        fn.decorator_list = []
        cls.source = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, row, *, mode="DEMO", scenario="san-1", incident="INC-147"):
        cursor = Cursor(row)

        @contextmanager
        def db():
            yield cursor

        namespace = {
            "db": db,
            "auth": lambda token: None,
            "bearer": lambda header: header,
            "Header": lambda default=None: default,
            "HTTPException": HTTPException,
            "new": lambda kind: "RUN-NEW",
            "STAGES": [],
            "append_event": lambda *args, **kwargs: None,
        }
        exec(self.source, namespace)
        request = SimpleNamespace(
            idempotency_key="stable-key", mode=mode,
            scenario_id=scenario, incident_id=incident,
        )
        try:
            result = namespace["create"](request, authorization="token")
        except HTTPException as exc:
            result = exc
        return result, cursor.calls

    def test_same_intent_returns_original_receipt_without_write(self):
        result, calls = self.invoke(("RUN-147", "DEMO", "san-1", "CREATED", 1, "INC-147"))
        self.assertEqual(result["run_id"], "RUN-147")
        self.assertEqual(result["mode"], "DEMO")
        self.assertEqual(len(calls), 1)
        self.assertIn("for update", calls[0][0].lower())

    def test_key_reuse_with_different_intent_fails_closed(self):
        existing = ("RUN-147", "DEMO", "san-1", "CREATED", 1, "INC-147")
        for kwargs in (
            {"mode": "LIVE"},
            {"scenario": "san-2"},
            {"incident": "INC-OTHER"},
            {"incident": None},
        ):
            with self.subTest(kwargs=kwargs):
                result, calls = self.invoke(existing, **kwargs)
                self.assertIsInstance(result, HTTPException)
                self.assertEqual(result.status_code, 409)
                self.assertEqual(len(calls), 1)

    def test_missing_stored_identity_is_not_a_match(self):
        result, calls = self.invoke(("RUN-147", "DEMO", "san-1", "CREATED", 1, None))
        self.assertEqual(result.status_code, 409)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
