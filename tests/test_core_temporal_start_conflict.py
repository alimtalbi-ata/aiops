"""Execute canonical Core start endpoint with fake DB and Worker HTTP transport.

No real Core/Postgres/Temporal; asserts ambiguous start outcomes never claim
idempotent execution and Worker conflicts remain visible to the operator.
"""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

SOURCE = Path(__file__).resolve().parents[1] / "app" / "core" / "main.py"


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code
        self.detail = detail


@pytest.mark.parametrize("kind,expected_code,expected_text", [
    ("conflict", 409, "reconciliation"),
    ("timeout", 503, "outcome unknown"),
    ("unavailable", 503, "HTTP failure"),
])
def test_core_start_failure_requires_reconciliation_without_receipt(kind, expected_code, expected_text):
    module = ast.parse(SOURCE.read_text())
    fn = next(n for n in module.body if isinstance(n, ast.FunctionDef)
              and n.name == "execute")
    fn.decorator_list = []
    statements = []
    class Connection:
        def execute(self, sql, params):
            statements.append(sql)
            if "from aiops.runs" in sql:
                return SimpleNamespace(fetchone=lambda: ("run-01", "DEMO", "acme", 0, "CREATED"))
            if "from aiops.execution_receipts" in sql:
                return SimpleNamespace(fetchone=lambda: None)
            raise AssertionError("unexpected SQL: " + sql)
    @contextmanager
    def db():
        yield Connection()
    def post(url, **kwargs):
        assert kwargs["json"] == {"run_id": "run-01", "mode": "DEMO",
                                   "scenario_id": "acme", "version": 0}
        if kind == "timeout":
            raise requests.Timeout("connection timed out")
        response = requests.Response()
        response.status_code = 409 if kind == "conflict" else 502
        response.url = url
        raise requests.HTTPError("worker rejected start", response=response)
    ns = {
        "db": db, "auth": lambda token: None,
        "bearer": lambda token: token,
        "Header": lambda default=None: default,
        "HTTPException": HttpError,
        "requests": SimpleNamespace(
            post=post, HTTPError=requests.HTTPError,
            RequestException=requests.RequestException),
        "WORKER": "http://worker", "ADMIN": "inert",
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    with pytest.raises(HttpError) as exc:
        ns["execute"]("run-01", authorization="Bearer inert")
    assert exc.value.status_code == expected_code
    assert expected_text in exc.value.detail
    assert not any("insert into aiops.execution_receipts" in sql for sql in statements)
