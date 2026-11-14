"""Execute actual Worker start endpoint with inert Temporal client."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


class HttpError(Exception):
    def __init__(self, code, detail):
        self.status_code, self.detail = code, detail


def endpoint():
    module = ast.parse(SOURCE.read_text())
    fn = next(n for n in module.body if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "start")
    fn.decorator_list = []
    calls = []
    class Client:
        @staticmethod
        async def connect(address):
            calls.append(("connect", address))
            class Connection:
                async def start_workflow(self, *args, **kwargs):
                    calls.append(("start", args, kwargs))
                    return SimpleNamespace(id=kwargs["id"])
            return Connection()
    def mode_contract(mode):
        if type(mode) is not str or mode not in ("DEMO", "LIVE"):
            raise ValueError("invalid mode")
        return "SIMULATE" if mode == "DEMO" else "REMEDIATE"
    ns = {
        "Header": lambda default=None: default,
        "HTTPException": HttpError,
        "Client": Client, "TEMP": "inert-temporal",
        "ADMIN": "trusted-token", "IncidentWorkflow": SimpleNamespace(run=lambda: None),
        "policy_command_for_mode": mode_contract,
        "WorkflowAlreadyStartedError": type("AlreadyStarted", (Exception,), {}),
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    return ns["start"], calls


@pytest.mark.parametrize("payload", [
    {}, {"run_id": "r", "mode": "DEMO", "scenario_id": "s"},
    {"run_id": "r", "mode": "DEMO", "scenario_id": "s", "version": True},
    {"run_id": "r", "mode": "DEMO", "scenario_id": "s", "version": -1},
    {"run_id": "../r", "mode": "DEMO", "scenario_id": "s", "version": 0},
    {"run_id": "r", "mode": "DEMO", "scenario_id": "s\n", "version": 0},
    {"run_id": "r", "mode": "DEMO", "scenario_id": "s", "version": 0, "tenant_id": "other"},
    {"run_id": "r", "mode": "FAKE", "scenario_id": "s", "version": 0},
    {"run_id": "r", "mode": ["DEMO"], "scenario_id": "s", "version": 0},
])
def test_invalid_envelope_refused_before_temporal(payload):
    start, calls = endpoint()
    with pytest.raises(HttpError) as exc:
        asyncio.run(start(payload, authorization="Bearer trusted-token"))
    assert exc.value.status_code == 422
    assert calls == []


def test_unauthorized_cannot_connect_to_temporal():
    start, calls = endpoint()
    with pytest.raises(HttpError) as exc:
        asyncio.run(start({"run_id": "r", "mode": "DEMO",
                           "scenario_id": "s", "version": 0},
                          authorization="Bearer wrong"))
    assert exc.value.status_code == 401
    assert calls == []


def test_valid_canonical_core_envelope_starts_once():
    start, calls = endpoint()
    result = asyncio.run(start({"run_id": "r-01", "mode": "DEMO",
                                "scenario_id": "acme", "version": 0},
                               authorization="Bearer trusted-token"))
    assert result["run_id"] == "r-01"
    assert [x[0] for x in calls] == ["connect", "start"]
    assert calls[1][2]["id"] == "r-01"
