"""LIVE command admission must fail closed before replaying historical receipts."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Cursor:
    def __init__(self, mode, receipt):
        self.mode, self.receipt = mode, receipt
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if not sql.lstrip().lower().startswith("select "):
            raise AssertionError("Admission denial must not write")
        return self

    def fetchone(self):
        if len(self.queries) == 1:
            return ("CREATED", 1, self.mode)
        return self.receipt


class LiveCommandAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "command")
        fn.decorator_list = []
        cls.code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, mode, command, receipt):
        cursor = Cursor(mode, receipt)

        @contextmanager
        def db():
            yield cursor

        scope = {
            "db": db,
            "auth": lambda token: None,
            "bearer": lambda header: header,
            "HTTPException": HTTPException,
        }
        exec(self.code, scope)
        request = SimpleNamespace(expected_version=1, idempotency_key="old-key", command=command)
        try:
            result = scope["command"]("RUN-147", request, authorization="token")
        except HTTPException as error:
            result = error
        return result, cursor.queries

    def test_live_start_and_resolve_denied_even_with_receipt(self):
        for command in ("START", "RESOLVE"):
            for receipt in (None, ("RUN-147", command, {"status": "RUNNING"})):
                with self.subTest(command=command, receipt=receipt):
                    result, queries = self.invoke("LIVE", command, receipt)
                    self.assertIsInstance(result, HTTPException)
                    self.assertEqual(result.status_code, 403)
                    self.assertEqual(len(queries), 1)

    def test_demo_start_receipt_still_idempotent(self):
        expected = {"run_id": "RUN-147", "status": "RUNNING", "version": 2}
        result, queries = self.invoke("DEMO", "START", ("RUN-147", "START", expected))
        self.assertEqual(result, expected)
        self.assertEqual(len(queries), 2)


if __name__ == "__main__":
    unittest.main()
