"""Fail closed when a persisted Run has a corrupt scenario identity.

Tests execute the real Core route body with a read-only fake cursor; no Worker,
PostgreSQL, GLPI or live runtime is contacted.
"""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

SOURCE = Path(__file__).resolve().parents[1] / "app/core/main.py"


def load_execute(db_factory, requests_stub):
    tree = ast.parse(SOURCE.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "execute")
    node.decorator_list = []
    ns = {
        "db": db_factory,
        "auth": lambda token: None,
        "bearer": lambda token: token,
        "Header": lambda default=None: default,
        "HTTPException": HTTPException,
        "requests": requests_stub,
        "WORKER": "http://unreachable.invalid",
        "ADMIN": "fake",
    }
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["execute"]


@pytest.mark.parametrize("scenario", [
    None, "", " ", " FS147", "FS147 ", "FS147\\n", "FS147\\x00", "FS147\\x7f"
])
def test_corrupt_persisted_scenario_denied_before_worker_and_receipt(scenario):
    queries = []
    class Cursor:
        def execute(self, query, params=()):
            queries.append(query)
            return self
        def fetchone(self):
            return ("RUN-147", "DEMO", scenario, 1, "CREATED")
    @contextmanager
    def db():
        yield Cursor()
    class NoNetwork:
        class RequestException(Exception):
            pass
        def post(self, *args, **kwargs):
            raise AssertionError("Worker must never be contacted")
    with pytest.raises(HTTPException) as exc:
        load_execute(db, NoNetwork())("RUN-147", authorization="token")
    assert exc.value.status_code == 422
    assert len(queries) == 1
    assert "execution_receipts" not in queries[0]


def test_valid_scenario_keeps_existing_idempotent_receipt():
    queries = []
    class Cursor:
        def execute(self, query, params=()):
            queries.append(query)
            return self
        def fetchone(self):
            if len(queries) == 1:
                return ("RUN-147", "DEMO", "FS147", 2, "WAITING")
            return ("RUN-147",)
    @contextmanager
    def db():
        yield Cursor()
    class NoNetwork:
        class RequestException(Exception):
            pass
        def post(self, *args, **kwargs):
            raise AssertionError("Receipt replay must not dispatch Worker")
    result = load_execute(db, NoNetwork())("RUN-147", authorization="token")
    assert result == {"run_id": "RUN-147", "workflow_id": "RUN-147", "idempotent": True}
    assert len(queries) == 2
