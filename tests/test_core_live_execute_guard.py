"""Regression: the actual Core execute route must not dispatch LIVE to Worker.

Offline AST extraction avoids importing application startup (which requires secrets/DB).
No network, DB, GLPI, or Temporal side effects.
"""
import ast
import pathlib
import unittest
from unittest.mock import Mock


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


class FakeDB:
    def __init__(self, mode, status="CREATED"):
        self.mode, self.status = mode, status
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.queries.append(query)
        return self

    def fetchone(self):
        return ("RUN-1", self.mode, "scenario", 1, self.status)


def load_execute(db_factory, requests):
    source = pathlib.Path(__file__).resolve().parents[1] / "app/core/main.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    function.decorator_list = []
    namespace = {
        "Header": lambda default=None: default,
        "HTTPException": HTTPException,
        "db": db_factory,
        "auth": lambda token: None,
        "bearer": lambda token: token,
        "requests": requests,
        "WORKER": "http://worker.invalid",
        "ADMIN": "offline-test",
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace["execute"]


class LiveExecutionGateTests(unittest.TestCase):
    def test_live_never_calls_worker_or_writes(self):
        for state in ("CREATED", "WAITING"):
            with self.subTest(state=state):
                connection = FakeDB("LIVE", state)
                requests = Mock()
                execute = load_execute(lambda: connection, requests)
                with self.assertRaises(HTTPException) as caught:
                    execute("RUN-1", "Bearer offline-test")
                self.assertEqual(caught.exception.status_code, 403)
                self.assertIn("Policy/HITL", caught.exception.detail)
                self.assertEqual(len(connection.queries), 1)
                self.assertTrue(connection.queries[0].lstrip().lower().startswith("select"))
                requests.post.assert_not_called()

    def test_non_executable_live_state_is_not_dispatched(self):
        connection = FakeDB("LIVE", "RESOLVED")
        requests = Mock()
        execute = load_execute(lambda: connection, requests)
        with self.assertRaises(HTTPException) as caught:
            execute("RUN-1", "Bearer offline-test")
        self.assertEqual(caught.exception.status_code, 409)
        requests.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
