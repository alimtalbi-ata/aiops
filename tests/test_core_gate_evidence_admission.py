"""Core gate admission regression: no DB writes on missing/unverified PASS evidence."""
import ast
from pathlib import Path
from contextlib import contextmanager

import pytest
from fastapi import HTTPException


SOURCE = Path(__file__).resolve().parents[1] / "app/core/main.py"


def load_gate(db_factory):
    source = ast.parse(SOURCE.read_text())
    node = next(n for n in source.body if isinstance(n, ast.FunctionDef) and n.name == "gate")
    node.decorator_list = []
    namespace = {"db": db_factory, "auth": lambda token: None,
                 "bearer": lambda value: value, "Header": lambda default=None: default,
                 "HTTPException": HTTPException, "json": __import__("json"),
                 "new": lambda prefix: prefix + "-test"}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["gate"]


class Cursor:
    def __init__(self, known=("EV-1",)):
        self.known = set(known)
        self.writes = []
        self.count = 0

    def execute(self, query, params=()):
        if query.lstrip().lower().startswith("insert"):
            self.writes.append((query, params))
        if "evidence_id=any" in query:
            self.count = len(self.known.intersection(params[0]))
        return self

    def fetchone(self):
        return (self.count if self.count else 1,)


@pytest.fixture
def fixture_gate():
    cursor = Cursor()
    @contextmanager
    def db():
        yield cursor
    return load_gate(db), cursor


@pytest.mark.parametrize("payload,status", [
    ({"state": "PASS"}, 409),
    ({"state": "PASS", "required_evidence": ["EV-1"]}, 409),
    ({"state": "PASS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-1", "EV-1"]}, 422),
    ({"state": "PASS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-2"]}, 409),
    ({"state": "PASS", "required_evidence": "EV-1", "evidence_ids": ["EV-1"]}, 422),
])
def test_gate_rejects_unverified_pass_without_write(fixture_gate, payload, status):
    gate, cursor = fixture_gate
    with pytest.raises(HTTPException) as error:
        gate("RUN-1", payload, authorization="token")
    assert error.value.status_code == status
    assert cursor.writes == []


def test_gate_accepts_persisted_required_evidence(fixture_gate):
    gate, cursor = fixture_gate
    result = gate("RUN-1", {"stage": "POLICY", "state": "PASS",
                             "required_evidence": ["EV-1"], "evidence_ids": ["EV-1"]},
                  authorization="token")
    assert result == {"run_id": "RUN-1", "stage": "POLICY", "state": "PASS"}
    assert len(cursor.writes) == 1


def test_gate_missing_persisted_evidence_fails_closed(fixture_gate):
    gate, cursor = fixture_gate
    cursor.known.clear()
    # A count of zero is returned by the evidence lookup, not the run lookup.
    original_execute = cursor.execute
    def execute(query, params=()):
        result = original_execute(query, params)
        if "evidence_id=any" in query:
            cursor.count = -1
        return result
    cursor.execute = execute
    with pytest.raises(HTTPException) as error:
        gate("RUN-1", {"state": "PASS", "required_evidence": ["EV-1"],
                        "evidence_ids": ["EV-1"]}, authorization="token")
    assert error.value.status_code == 422
    assert not cursor.writes
