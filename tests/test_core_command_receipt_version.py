"""Regression: command receipt must bind original optimistic version and response."""
import ast
import json
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class Cursor:
    def __init__(self, receipt):
        self.receipt = receipt
        self.calls = []
        self.last = ""

    def execute(self, sql, params=None):
        self.last = sql
        self.calls.append(sql)
        return self

    def fetchone(self):
        if "from aiops.runs where run_id" in self.last:
            return ("RUNNING", 4, "DEMO")
        if "from aiops.command_receipts" in self.last:
            return self.receipt
        raise AssertionError(self.last)


class ReceiptVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "command")
        fn.decorator_list = []
        cls.code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, expected_version, receipt):
        cursor = Cursor(receipt)
        @contextmanager
        def db():
            yield cursor
        scope = {"db": db, "auth": lambda token: None, "bearer": lambda token: token,
                 "HTTPException": HTTPException, "json": json}
        exec(self.code, scope)
        request = SimpleNamespace(command="START", expected_version=expected_version,
                                  idempotency_key="same-key")
        try:
            result = scope["command"]("RUN-147", request, authorization="token")
        except HTTPException as exc:
            result = exc
        return result, cursor.calls

    def receipt(self, response):
        return ("RUN-147", "START", response)

    def test_identical_retry_returns_original_receipt(self):
        result, calls = self.invoke(3, self.receipt({"run_id": "RUN-147", "status": "RUNNING", "version": 4}))
        self.assertEqual(result["version"], 4)
        self.assertEqual(len(calls), 2)

    def test_reused_key_with_new_expected_version_conflicts(self):
        result, calls = self.invoke(4, self.receipt({"run_id": "RUN-147", "status": "RUNNING", "version": 4}))
        self.assertEqual(result.status_code, 409)
        self.assertEqual(len(calls), 2)

    def test_foreign_or_malformed_receipt_never_succeeds(self):
        for response in ({"run_id": "RUN-OTHER", "status": "RUNNING", "version": 4},
                         {"run_id": "RUN-147", "status": "RESOLVED", "version": 4},
                         {"run_id": "RUN-147", "status": "RUNNING", "version": True},
                         "invalid json", None):
            with self.subTest(response=response):
                result, calls = self.invoke(3, self.receipt(response))
                self.assertEqual(result.status_code, 409)
                self.assertEqual(len(calls), 2)

    def test_json_encoded_receipt_accepted(self):
        response = json.dumps({"run_id": "RUN-147", "status": "RUNNING", "version": 4})
        result, _ = self.invoke(3, self.receipt(response))
        self.assertEqual(result["run_id"], "RUN-147")


if __name__ == "__main__":
    unittest.main()
