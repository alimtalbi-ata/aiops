"""Core checkpoint workflow identity regression, isolated from DB and network."""
import ast
from contextlib import contextmanager
from pathlib import Path
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class Cursor:
    def __init__(self):
        self.writes = []

    def execute(self, sql, params):
        self.writes.append((sql, params))


class CheckpointIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "checkpoint")
        fn.decorator_list = []
        cls.code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, workflow_id):
        cursor = Cursor()

        @contextmanager
        def db():
            yield cursor

        namespace = {
            "db": db, "auth": lambda _: None, "bearer": lambda x: x,
            "Header": lambda default=None: default, "HTTPException": HTTPException,
        }
        exec(self.code, namespace)
        payload = {"stage": "INGEST", "version": 1, "workflow_id": workflow_id}
        try:
            result = namespace["checkpoint"]("RUN-147", payload, authorization="token")
        except HTTPException as exc:
            result = exc
        return result, cursor.writes

    def test_canonical_workflow_is_persisted(self):
        result, writes = self.invoke("RUN-147")
        self.assertEqual(result["run_id"], "RUN-147")
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][1][-1], "RUN-147")

    def test_foreign_or_invalid_workflow_is_rejected_before_db(self):
        for value in ("RUN-OTHER", "", 147, False, [], {}):
            with self.subTest(value=value):
                result, writes = self.invoke(value)
                self.assertIsInstance(result, HTTPException)
                self.assertEqual(result.status_code, 409)
                self.assertEqual(writes, [])

    def test_absent_workflow_remains_unverified_not_fabricated(self):
        result, writes = self.invoke(None)
        self.assertEqual(result["run_id"], "RUN-147")
        self.assertEqual(writes[0][1][-1], None)


if __name__ == "__main__":
    unittest.main()
