"""Regression contract for incident external-id source/synthetic ownership."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import unittest


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


class Cursor:
    def __init__(self, saved):
        self.saved = saved
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.saved


class IncidentIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "app/core/main.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "incident")
        fn.decorator_list = []
        cls.code = compile(ast.Module(body=[fn], type_ignores=[]), str(path), "exec")

    def invoke(self, saved, source="simulator", synthetic=True):
        cursor = Cursor(saved)

        @contextmanager
        def db():
            yield cursor

        scope = {
            "db": db,
            "auth": lambda token: None,
            "bearer": lambda token: token,
            "HTTPException": HTTPException,
            "json": __import__("json"),
        }
        exec(self.code, scope)
        req = SimpleNamespace(
            external_id="FS147", title="FS event", severity="P2",
            service_id=None, source=source, synthetic=synthetic, payload={}
        )
        try:
            result = scope["incident"](req, authorization="token")
        except HTTPException as exc:
            result = exc
        return result, cursor.calls

    def test_conflict_without_matching_identity_fails_closed(self):
        for source, synthetic in (("san-monitor", False), ("simulator", False), ("san-monitor", True)):
            with self.subTest(source=source, synthetic=synthetic):
                result, calls = self.invoke(None, source, synthetic)
                self.assertIsInstance(result, HTTPException)
                self.assertEqual(result.status_code, 409)
                self.assertEqual(len(calls), 1)
                sql, params = calls[0]
                self.assertIn("on conflict(external_id)", sql.lower())
                self.assertIn("aiops.incidents.source is not distinct from excluded.source", sql.lower())
                self.assertIn("aiops.incidents.synthetic is not distinct from excluded.synthetic", sql.lower())
                self.assertIn("returning incident_id", sql.lower())
                self.assertEqual(params[5:7], (source, synthetic))

    def test_same_identity_is_replayable(self):
        result, calls = self.invoke(("INC-CANONICAL-EXISTING",))
        self.assertEqual(result["incident_id"], "INC-CANONICAL-EXISTING")
        self.assertEqual(result["synthetic"], True)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
