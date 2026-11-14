"""Execute Core's read-only Temporal inspection endpoint with inert DB/HTTP."""
import ast
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

SOURCE = Path(__file__).resolve().parents[1] / "app" / "core" / "main.py"


class HttpError(Exception):
    def __init__(self, code, detail):
        self.status_code, self.detail = code, detail


def endpoint(*, response_kind="valid", receipt=None):
    module = ast.parse(SOURCE.read_text())
    fn = next(n for n in module.body if isinstance(n, ast.FunctionDef)
              and n.name == "inspect_run_execution")
    fn.decorator_list = []
    calls = []
    class Connection:
        def execute(self, sql, params):
            calls.append(("sql", sql))
            if "from aiops.runs" in sql:
                return SimpleNamespace(fetchone=lambda: ("run-01", "DEMO", "acme", 0, "CREATED"))
            if "from aiops.execution_receipts" in sql:
                return SimpleNamespace(fetchone=lambda: receipt)
            raise AssertionError(sql)
    @contextmanager
    def db():
        yield Connection()
    def get(url, **kwargs):
        calls.append(("get", url))
        if response_kind == "timeout":
            raise requests.Timeout("inert timeout")
        payload = {
            "run_id": "run-01", "workflow_id": "run-01",
            "temporal_visibility": "EXISTS_UNATTESTED",
            "status_observed": "RUNNING",
            "original_start_arguments_verified": False,
            "core_receipt_verified": False,
            "idempotent_start_confirmed": False,
            "live_remediation_authorized": False,
        }
        if response_kind == "forged":
            payload["idempotent_start_confirmed"] = True
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
    ns = {
        "db": db, "auth": lambda token: None, "bearer": lambda token: token,
        "Header": lambda default=None: default, "HTTPException": HttpError,
        "requests": SimpleNamespace(get=get, RequestException=requests.RequestException),
        "WORKER": "http://worker", "ADMIN": "inert",
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["inspect_run_execution"], calls


@pytest.mark.parametrize("receipt", [None, ("run-01",), ("other-run",)])
def test_observation_is_unattested_and_never_writes(receipt):
    inspect, calls = endpoint(receipt=receipt)
    result = inspect("run-01", authorization="Bearer inert")
    assert result["temporal_visibility"] == "EXISTS_UNATTESTED"
    assert result["core_execution_receipt_present"] is (receipt is not None)
    assert result["core_receipt_workflow_id_matches"] is (receipt == ("run-01",))
    assert result["execution_start_outcome"] == "UNKNOWN"
    assert result["automatic_reconciliation_performed"] is False
    assert result["live_remediation_authorized"] is False
    assert not any("insert" in sql.lower() or "update" in sql.lower()
                   for kind, sql in calls if kind == "sql")
    assert [kind for kind, _ in calls].count("get") == 1


@pytest.mark.parametrize("kind", ["timeout", "forged"])
def test_unavailable_or_forged_worker_response_fails_closed(kind):
    inspect, calls = endpoint(response_kind=kind)
    with pytest.raises(HttpError) as exc:
        inspect("run-01", authorization="Bearer inert")
    assert exc.value.status_code == 503


def test_bad_run_id_denied_before_database_or_network():
    inspect, calls = endpoint()
    with pytest.raises(HttpError) as exc:
        inspect("../run", authorization="Bearer inert")
    assert exc.value.status_code == 422
    assert calls == []
