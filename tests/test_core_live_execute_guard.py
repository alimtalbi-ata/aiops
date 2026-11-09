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
    def __init__(self, mode, status="CREATED", receipt=None):
        self.mode, self.status, self.receipt = mode, status, receipt
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, query, params):
        self.queries.append(query)
        return self

    def fetchone(self):
        if self.queries[-1].lstrip().lower().startswith("select workflow_id"):
            return (self.receipt,) if self.receipt is not None else None
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

    def test_corrupt_persisted_modes_never_dispatch(self):
        for mode in (None, "", "UNKNOWN", "live", "LIVE ", "SIMULATION", False, 0):
            for state in ("CREATED", "WAITING"):
                with self.subTest(mode=mode, state=state):
                    connection = FakeDB(mode, state)
                    requests = Mock()
                    execute = load_execute(lambda: connection, requests)
                    with self.assertRaises(HTTPException) as caught:
                        execute("RUN-1", "Bearer offline-test")
                    self.assertEqual(caught.exception.status_code, 422)
                    self.assertEqual(len(connection.queries), 1)
                    self.assertTrue(connection.queries[0].lstrip().lower().startswith("select"))
                    requests.post.assert_not_called()

    def test_non_live_retry_after_progression_returns_durable_receipt(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            for status in ("RUNNING", "RESOLVED", "FAILED"):
                with self.subTest(mode=mode, status=status):
                    connection = FakeDB(mode, status, receipt="wf-existing")
                    requests = Mock()
                    result = load_execute(lambda: connection, requests)("RUN-1", "Bearer offline-test")
                    self.assertEqual(result, {"run_id": "RUN-1", "workflow_id": "wf-existing", "idempotent": True})
                    self.assertEqual(len(connection.queries), 2)
                    requests.post.assert_not_called()

    def test_non_live_progressed_without_receipt_fails_closed(self):
        connection = FakeDB("DEMO", "RUNNING")
        requests = Mock()
        with self.assertRaises(HTTPException) as caught:
            load_execute(lambda: connection, requests)("RUN-1", "Bearer offline-test")
        self.assertEqual(caught.exception.status_code, 409)
        requests.post.assert_not_called()

    def test_receipt_without_workflow_id_never_returns_success(self):
        connection = FakeDB("DEMO", "WAITING", receipt="")
        requests = Mock()
        with self.assertRaises(HTTPException) as caught:
            load_execute(lambda: connection, requests)("RUN-1", "Bearer offline-test")
        self.assertEqual(caught.exception.status_code, 409)
        requests.post.assert_not_called()

    def test_worker_receipt_identity_must_match_run_before_persistence(self):
        for response in (
            None, [], "ok", {},
            {"run_id": "RUN-OTHER", "workflow_id": "RUN-1"},
            {"run_id": "RUN-1", "workflow_id": "RUN-OTHER"},
            {"run_id": "RUN-1", "workflow_id": None},
            {"run_id": "RUN-1", "workflow_id": ""},
        ):
            with self.subTest(response=response):
                connection = FakeDB("DEMO", "CREATED")
                requests = Mock()
                requests.post.return_value.json.return_value = response
                with self.assertRaises(HTTPException) as caught:
                    load_execute(lambda: connection, requests)("RUN-1", "Bearer offline-test")
                self.assertEqual(caught.exception.status_code, 502)
                self.assertEqual(len(connection.queries), 2)
                self.assertTrue(all(q.lstrip().lower().startswith("select") for q in connection.queries))
                requests.post.assert_called_once()

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
