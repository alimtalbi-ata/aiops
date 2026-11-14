"""Offline fail-closed checks for one-shot Core execution intent."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app/core/main.py"


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


def test_prior_intent_blocks_network_before_retry():
    tree = ast.parse(SOURCE.read_text())
    fn = next(node for node in tree.body
              if isinstance(node, ast.FunctionDef) and node.name == "execute")
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
                return SimpleNamespace(fetchone=lambda: None)
            raise AssertionError(sql)

    @contextmanager
    def db():
        yield Connection()

    def post(*args, **kwargs):
        raise AssertionError("must never contact Temporal for a prior intent")

    ns = {"db": db, "auth": lambda _: None, "bearer": lambda x: x,
          "Header": lambda default=None: default, "HTTPException": HttpError,
          "requests": SimpleNamespace(post=post),
          "WORKER": "http://worker", "ADMIN": "inert"}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    with pytest.raises(HttpError) as exc:
        ns["execute"]("run-01", authorization="Bearer inert")
    assert exc.value.status_code == 409
    assert any("insert into aiops.execution_start_intents" in sql
               for sql in statements)


def test_immutable_schema_has_mutation_guard():
    sql = (SOURCE.parents[1] / "db/migrations/013_execution_start_intents.sql").read_text()
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "RAISE EXCEPTION" in sql
    assert "PRIMARY KEY REFERENCES aiops.runs(run_id)" in sql
