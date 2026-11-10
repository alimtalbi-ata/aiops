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
    ({"stage": "POLICY", "state": "PASS"}, 409),
    ({"stage": "POLICY", "state": "PASS", "required_evidence": ["EV-1"]}, 409),
    ({"stage": "POLICY", "state": "PASS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-1", "EV-1"]}, 422),
    ({"stage": "POLICY", "state": "PASS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-2"]}, 409),
    ({"stage": "POLICY", "state": "PASS", "required_evidence": "EV-1", "evidence_ids": ["EV-1"]}, 422),
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
        gate("RUN-1", {"stage": "POLICY", "state": "PASS", "required_evidence": ["EV-1"],
                        "evidence_ids": ["EV-1"]}, authorization="token")
    assert error.value.status_code == 422
    assert not cursor.writes


def test_gate_upsert_reconciles_required_evidence_on_repeated_stage(fixture_gate):
    """A changed stage contract must not leave stale required_evidence in DB."""
    gate, cursor = fixture_gate
    gate("RUN-1", {"stage": "POLICY", "state": "PASS",
                   "required_evidence": ["EV-1"], "evidence_ids": ["EV-1"]},
         authorization="token")
    gate("RUN-1", {"stage": "POLICY", "state": "UNKNOWN",
                   "required_evidence": [], "evidence_ids": []},
         authorization="token")
    assert len(cursor.writes) == 2
    first_sql, first_params = cursor.writes[0]
    second_sql, second_params = cursor.writes[1]
    assert "required_evidence=excluded.required_evidence" in first_sql
    assert "required_evidence=excluded.required_evidence" in second_sql
    assert first_params[4] == '["EV-1"]'
    assert second_params[4] == "[]"
    assert second_params[3] == "UNKNOWN"


@pytest.mark.parametrize("payload", [
    {"state": "PASS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-1"]},
    {"stage": "", "state": "PASS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-1"]},
    {"stage": None, "state": "UNKNOWN"},
    {"stage": "POLICY", "state": None},
    {"stage": "POLICY", "state": "SUCCESS", "required_evidence": ["EV-1"], "evidence_ids": ["EV-1"]},
])
def test_gate_unknown_stage_or_state_cannot_write(fixture_gate, payload):
    gate, cursor = fixture_gate
    with pytest.raises(HTTPException) as exc:
        gate("RUN-1", payload, authorization="token")
    assert exc.value.status_code == 422
    assert cursor.writes == []


def test_gate_explicit_unknown_state_is_not_pass(fixture_gate):
    gate, cursor = fixture_gate
    result = gate("RUN-1", {"stage": "POLICY", "state": "UNKNOWN",
                             "required_evidence": [], "evidence_ids": []},
                  authorization="token")
    assert result["state"] == "UNKNOWN"
    assert cursor.writes[0][1][3] == "UNKNOWN"


@pytest.mark.parametrize("stage", [
    " POLICY", "POLICY ", "POLICY\\n", "POLICY\\t", "POLICY\\x00", "POLICY\\x7f",
])
def test_gate_rejects_ambiguous_stage_alias_without_write(fixture_gate, stage):
    gate, cursor = fixture_gate
    with pytest.raises(HTTPException) as exc:
        gate("RUN-1", {"stage": stage, "state": "UNKNOWN",
                       "required_evidence": [], "evidence_ids": []},
             authorization="token")
    assert exc.value.status_code == 422
    assert cursor.writes == []


def test_gate_canonical_stage_still_accepts_unknown(fixture_gate):
    gate, cursor = fixture_gate
    result = gate("RUN-1", {"stage": "POLICY", "state": "UNKNOWN",
                            "required_evidence": [], "evidence_ids": []},
                  authorization="token")
    assert result["stage"] == "POLICY"
    assert result["state"] == "UNKNOWN"
    assert len(cursor.writes) == 1


@pytest.mark.parametrize("field,bad_id", [
    ("evidence_ids", " EV-1"),
    ("evidence_ids", "EV-1 "),
    ("evidence_ids", "EV-1\\n"),
    ("evidence_ids", "EV-1\\x00"),
    ("required_evidence", " EV-1"),
    ("required_evidence", "EV-1\\t"),
    ("required_evidence", "EV-1\\x7f"),
])
def test_gate_rejects_noncanonical_evidence_identity_before_write(fixture_gate, field, bad_id):
    gate, cursor = fixture_gate
    payload = {"stage": "POLICY", "state": "UNKNOWN",
               "required_evidence": [], "evidence_ids": []}
    payload[field] = [bad_id]
    with pytest.raises(HTTPException) as exc:
        gate("RUN-1", payload, authorization="token")
    assert exc.value.status_code == 422
    assert cursor.writes == []
