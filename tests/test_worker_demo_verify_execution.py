"""Execute the actual Worker stage body with inert Core/Evidence stubs.

This is not a Temporal server E2E: it verifies the real async activity logic
without importing the Worker service or contacting any external component.
"""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "worker" / "main.py"


def _execute_stage_function(calls):
    source = SOURCE.read_text()
    module = ast.parse(source)
    fn = next(node for node in module.body
              if isinstance(node, ast.AsyncFunctionDef) and node.name == "execute_stage")
    # Strip Temporal decorator, but execute the unmodified function body.
    fn.decorator_list = []
    def core_call(method, url, payload):
        calls.append(("core", url, payload))
        if url.endswith("/events"):
            return {"version": 8, "sequence": 3}
        if url.endswith("/command"):
            return {"version": 9, "status": "BLOCKED"}
        raise AssertionError("unexpected Core call")
    def external_post(*args, **kwargs):
        calls.append(("external", args, kwargs))
        raise AssertionError("external side effect must not occur")
    namespace = {
        "CORE": "http://core", "EVID": "http://evidence",
        "POLICY": "http://policy", "TWIN": "http://twin",
        "ADMIN": "dummy", "call": core_call, "post_json": external_post,
        "policy_command_for_mode": lambda mode: "SIMULATE" if mode == "DEMO" else "DENY",
        "activity": SimpleNamespace(info=lambda: SimpleNamespace(attempt=1)),
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["execute_stage"]


def test_demo_verify_blocks_before_any_evidence_or_postcheck_pass():
    calls = []
    execute = _execute_stage_function(calls)
    result = asyncio.run(execute({
        "run_id": "demo-run-01", "version": 7, "stage": "VERIFY",
        "mode": "DEMO", "scenario_id": "acme-synthetic",
    }))
    assert result == {
        "run_id": "demo-run-01", "stage": "VERIFY",
        "status": "BLOCKED", "version": 9, "sequence": 3,
    }
    assert len(calls) == 3
    assert all(item[0] == "core" for item in calls)
    started, blocked, command = [item[2] for item in calls]
    assert started["event_type"] == "STAGE_STARTED"
    assert blocked["event_type"] == "INDEPENDENT_POSTCHECK_MISSING"
    assert blocked["status"] == "BLOCKED"
    assert blocked["payload"]["actual_recovery_state"] == "UNKNOWN"
    assert blocked["payload"]["independent_runtime_postcheck_verified"] is False
    assert command["command"] == "BLOCK"
    assert command["idempotency_key"] == "DEMO-POSTCHECK-BLOCK-demo-run-01"
    assert not any(item[2].get("event_type") == "STAGE_COMPLETED" for item in calls)


def test_live_verify_still_blocks_without_live_adapter():
    calls = []
    execute = _execute_stage_function(calls)
    result = asyncio.run(execute({
        "run_id": "live-run-01", "version": 7, "stage": "VERIFY",
        "mode": "LIVE", "scenario_id": "acme",
    }))
    assert result["status"] == "BLOCKED"
    assert len(calls) == 3
    assert calls[1][2]["event_type"] == "LIVE_ADAPTER_UNAVAILABLE"
    assert calls[2][2]["command"] == "BLOCK"
    assert all(item[0] == "core" for item in calls)
