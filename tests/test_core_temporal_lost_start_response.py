"""Simulate Temporal accepting a start while its HTTP response is lost.

Core must persist intent before network I/O and refuse a second POST even
without a receipt. This is an offline failure-injection contract, not Temporal E2E.
"""
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


def test_lost_response_after_temporal_acceptance_never_restarts():
    tree = ast.parse(SOURCE.read_text())
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "execute")
    fn.decorator_list = []
    persisted = {"intent": None, "receipt": None, "temporal_started": False}
    posts = []

    class Connection:
        def execute(self, sql, params):
            if "from aiops.runs" in sql:
                return SimpleNamespace(fetchone=lambda:
                    ("run-01", "DEMO", "acme", 1, "CREATED"))
            if "from aiops.execution_receipts" in sql:
                return SimpleNamespace(fetchone=lambda: persisted["receipt"])
            if "insert into aiops.execution_start_intents" in sql:
                assert params == ("run-01", "DEMO", "acme", 1)
                if persisted["intent"] is not None:
                    return SimpleNamespace(fetchone=lambda: None)
                persisted["intent"] = params
                return SimpleNamespace(fetchone=lambda: ("run-01",))
            raise AssertionError(sql)

    @contextmanager
    def db():
        yield Connection()

    def post(url, **kwargs):
        assert persisted["intent"] is not None
        posts.append(kwargs["json"])
        # Temporal has accepted it, but the HTTP response never reaches Core.
        persisted["temporal_started"] = True
        raise requests.Timeout("response lost after acceptance")

    ns = {"db": db, "auth": lambda _: None, "bearer": lambda x: x,
          "Header": lambda default=None: default, "HTTPException": HttpError,
          "requests": SimpleNamespace(
              post=post, HTTPError=requests.HTTPError,
              RequestException=requests.RequestException),
          "WORKER": "http://worker", "ADMIN": "inert"}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)

    with pytest.raises(HttpError) as first:
        ns["execute"]("run-01", authorization="Bearer inert")
    assert first.value.status_code == 503
    assert persisted["temporal_started"] is True
    assert persisted["receipt"] is None

    with pytest.raises(HttpError) as second:
        ns["execute"]("run-01", authorization="Bearer inert")
    assert second.value.status_code == 409
    assert "prior execution start intent" in second.value.detail
    assert len(posts) == 1
