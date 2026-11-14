"""Worker success must be bound to the requested Core run before receipt insert."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

SOURCE = Path(__file__).resolve().parents[1] / "app/core/main.py"


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


@pytest.mark.parametrize("worker_payload", [
    {"workflow_id": "other", "run_id": "run-01", "executor": "temporal"},
    {"workflow_id": "run-01", "run_id": "other", "executor": "temporal"},
    {"workflow_id": "run-01", "run_id": "run-01", "executor": "unknown"},
    {"workflow_id": "run-01", "run_id": "run-01",
     "executor": "temporal", "idempotent": True},
    {}, [], None,
])
def test_forged_worker_success_never_writes_execution_receipt(worker_payload):
    tree = ast.parse(SOURCE.read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "execute")
    fn.decorator_list = []
    statements = []

    class Connection:
        def execute(self, sql, params):
            statements.append(sql)
            if "from aiops.runs" in sql:
                return SimpleNamespace(fetchone=lambda:
                    ("run-01", "DEMO", "acme", 0, "CREATED"))
            if "from aiops.execution_receipts" in sql:
                return SimpleNamespace(fetchone=lambda: None)
            if "insert into aiops.execution_start_intents" in sql:
                return SimpleNamespace(fetchone=lambda: ("run-01",))
            raise AssertionError(sql)

    @contextmanager
    def db():
        yield Connection()

    def post(*args, **kwargs):
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: worker_payload,
        )

    ns = {"db": db, "auth": lambda _: None, "bearer": lambda x: x,
          "Header": lambda default=None: default, "HTTPException": HttpError,
          "requests": SimpleNamespace(post=post, HTTPError=requests.HTTPError,\n                                      RequestException=requests.RequestException),
          "WORKER": "http://worker", "ADMIN": "inert"}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    with pytest.raises(HttpError) as exc:
        ns["execute"]("run-01", authorization="Bearer inert")
    assert exc.value.status_code == 503
    assert not any("insert into aiops.execution_receipts" in sql
                   for sql in statements)
