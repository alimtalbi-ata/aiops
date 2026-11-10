"""Checkpoint stage identity regression: reject ambiguous Temporal stage aliases before DB."""
import ast
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi import HTTPException

SOURCE = Path(__file__).resolve().parents[1] / "app/core/main.py"


def load_checkpoint(db_factory):
    module = ast.parse(SOURCE.read_text())
    node = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "checkpoint")
    node.decorator_list = []
    ns = {"db": db_factory, "auth": lambda token: None,
          "bearer": lambda value: value,
          "Header": lambda default=None: default,
          "HTTPException": HTTPException}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["checkpoint"]


@pytest.mark.parametrize("stage", [
    "", " ", " POLICY", "POLICY ", "POLICY\n", "POLICY\t",
    "POLICY\x00", "POLICY\x7f", None, 17,
])
def test_checkpoint_rejects_ambiguous_stage_before_db(stage):
    calls = []
    @contextmanager
    def db():
        calls.append("entered")
        yield None
    checkpoint = load_checkpoint(db)
    with pytest.raises(HTTPException) as exc:
        checkpoint("RUN-1", {"stage": stage, "version": 1}, authorization="token")
    assert exc.value.status_code == 422
    assert calls == []


def test_checkpoint_canonical_stage_reaches_transaction():
    calls = []
    class Cursor:
        def execute(self, query, params=()):
            calls.append((query, params))
            return self
        def fetchone(self):
            return ("RUN-1",)
    @contextmanager
    def db():
        yield Cursor()
    result = load_checkpoint(db)("RUN-1", {
        "stage": "POLICY", "version": 1, "workflow_id": "RUN-1"
    }, authorization="token")
    assert result == {"run_id": "RUN-1", "stage": "POLICY", "version": 1}
    assert len(calls) == 1
    assert calls[0][1] == ("RUN-1", "POLICY", 1, "RUN-1")
