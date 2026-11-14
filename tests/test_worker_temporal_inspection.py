"""Execute the internal Temporal visibility endpoint with an inert client."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


class HttpError(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


def inspection(*, available=True):
    module = ast.parse(SOURCE.read_text())
    fn = next(n for n in module.body if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "inspect_execution")
    fn.decorator_list = []
    calls = []
    class Client:
        @staticmethod
        async def connect(address):
            calls.append(("connect", address))
            if not available:
                raise RuntimeError("Temporal unreachable")
            class Connection:
                def get_workflow_handle(self, run_id):
                    calls.append(("get_handle", run_id))
                    class Handle:
                        async def describe(self):
                            calls.append(("describe", run_id))
                            return SimpleNamespace(status="RUNNING")
                        async def fetch_history(self):
                            calls.append(("fetch_history", run_id))
                            return SimpleNamespace(events=[])
                    return Handle()
            return Connection()
    ns = {"decode_initial_start_args": lambda events: None, "Client": Client, "TEMP": "inert-temporal",
          "ADMIN": "internal-only", "HTTPException": HttpError,
          "Header": lambda default=None: default}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["inspect_execution"], calls


def test_read_only_visibility_never_attests_original_start_or_core_receipt():
    inspect, calls = inspection()
    result = asyncio.run(inspect("run-01", authorization="Bearer internal-only"))
    assert result["temporal_visibility"] == "EXISTS_UNATTESTED"
    assert result["status_observed"] == "RUNNING"
    assert result["original_start_arguments_verified"] is False
    assert result["core_receipt_verified"] is False
    assert result["idempotent_start_confirmed"] is False
    assert result["live_remediation_authorized"] is False
    assert [name for name, _ in calls] == ["connect", "get_handle", "describe", "fetch_history"]


@pytest.mark.parametrize("run_id", ["../bad", "a\n", "", "é", "a" * 129])
def test_invalid_identifier_never_connects(run_id):
    inspect, calls = inspection()
    with pytest.raises(HttpError) as exc:
        asyncio.run(inspect(run_id, authorization="Bearer internal-only"))
    assert exc.value.status_code == 422
    assert calls == []


def test_unauthorized_inspection_never_connects():
    inspect, calls = inspection()
    with pytest.raises(HttpError) as exc:
        asyncio.run(inspect("run-01", authorization="Bearer wrong"))
    assert exc.value.status_code == 401
    assert calls == []


def test_unavailable_temporal_fails_closed_without_claiming_absence():
    inspect, calls = inspection(available=False)
    with pytest.raises(HttpError) as exc:
        asyncio.run(inspect("run-01", authorization="Bearer internal-only"))
    assert exc.value.status_code == 503
    assert "unverified" in exc.value.detail
    assert [name for name, _ in calls] == ["connect"]
