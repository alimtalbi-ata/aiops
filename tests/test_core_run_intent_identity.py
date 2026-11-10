"""Run intent identity must fail closed before idempotency locks or inserts."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

SOURCE = Path(__file__).resolve().parents[1] / "app/core/main.py"


def load_create(db_factory):
    tree = ast.parse(SOURCE.read_text())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "create")
    node.decorator_list = []
    ns = {"db": db_factory, "auth": lambda token: None,
          "bearer": lambda value: value,
          "Header": lambda default=None: default,
          "HTTPException": HTTPException}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["create"]


@pytest.mark.parametrize(("field", "bad"), [
    ("scenario_id", ""), ("scenario_id", " FS147"),
    ("scenario_id", "FS147\n"), ("scenario_id", "FS147\x00"),
    ("idempotency_key", " "), ("idempotency_key", " key"),
    ("idempotency_key", "key\t"), ("idempotency_key", "key\x7f"),
    ("incident_id", ""), ("incident_id", " INC-1"),
    ("incident_id", "INC-1\n"), ("incident_id", "INC-1\x00"),
])
def test_ambiguous_run_intent_rejected_before_db(field, bad):
    entered = []
    @contextmanager
    def db():
        entered.append(True)
        yield None
    x = SimpleNamespace(mode="DEMO", scenario_id="FS147",
                        idempotency_key="key-147", incident_id="INC-147")
    setattr(x, field, bad)
    with pytest.raises(HTTPException) as exc:
        load_create(db)(x, authorization="token")
    assert exc.value.status_code == 422
    assert entered == []


def test_valid_replay_still_returns_existing_run():
    queries = []
    class Cursor:
        def execute(self, query, params=()):
            queries.append((query, params))
            return self
        def fetchone(self):
            return None if len(queries) == 1 else (
                "RUN-147", "DEMO", "FS147", "BLOCKED", 3, "INC-147"
            )
    @contextmanager
    def db():
        yield Cursor()
    x = SimpleNamespace(mode="DEMO", scenario_id="FS147",
                        idempotency_key="key-147", incident_id="INC-147")
    result = load_create(db)(x, authorization="token")
    assert result == {"run_id": "RUN-147", "mode": "DEMO",
                      "scenario_id": "FS147", "status": "BLOCKED", "version": 3}
    assert len(queries) == 2
    assert "pg_advisory_xact_lock" in queries[0][0]
