"""Regression: Core command idempotency keys cannot alias another Run/command."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Cursor:
    def __init__(self, receipt):
        self.receipt = receipt
        self.queries = []

    def execute(self, query, params):
        self.queries.append((query, params))
        if not query.lower().lstrip().startswith("select "):
            raise AssertionError("Receipt retry must never write")
        return self

    def fetchone(self):
        return ("CREATED", 1, "DEMO") if len(self.queries) == 1 else self.receipt


class CommandReceiptIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "command")
        fn.decorator_list = []
        cls.code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, receipt, *, rid="RUN-147", command="START"):
        cursor = Cursor(receipt)

        @contextmanager
        def db():
            yield cursor

        scope = {
            "db": db,
            "Header": lambda default=None: default,
            "Command": SimpleNamespace,
            "auth": lambda token: None,
            "bearer": lambda header: header,
            "HTTPException": HTTPException,
        }
        exec(self.code, scope)
        request = SimpleNamespace(expected_version=1, idempotency_key="shared-key", command=command)
        try:
            result = scope["command"](rid, request, authorization="token")
        except HTTPException as exc:
            result = exc
        return result, cursor.queries

    def test_identical_retry_returns_original_receipt(self):
        receipt = ("RUN-147", "START", {"run_id": "RUN-147", "status": "RUNNING", "version": 2})
        result, queries = self.invoke(receipt)
        self.assertEqual(result, receipt[2])
        self.assertEqual(len(queries), 2)
        self.assertIn("select run_id,command,response", queries[1][0].lower())

    def test_foreign_run_never_receives_receipt(self):
        result, queries = self.invoke(("RUN-OTHER", "START", {"run_id": "RUN-OTHER"}))
        self.assertEqual(result.status_code, 409)
        self.assertEqual(len(queries), 2)

    def test_different_command_never_receives_receipt(self):
        result, queries = self.invoke(("RUN-147", "RESOLVE", {"run_id": "RUN-147"}))
        self.assertEqual(result.status_code, 409)
        self.assertEqual(len(queries), 2)

    def test_unknown_receipt_identity_fails_closed(self):
        for receipt in ((None, "START", {}), ("RUN-147", None, {})):
            with self.subTest(receipt=receipt):
                result, queries = self.invoke(receipt)
                self.assertEqual(result.status_code, 409)
                self.assertEqual(len(queries), 2)


if __name__ == "__main__":
    unittest.main()
