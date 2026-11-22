"""Execute actual Worker POLICY stage against a refused Policy decision."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


@pytest.mark.parametrize("state", ["BLOCKED", "UNKNOWN"])
def test_policy_refusal_persists_core_block_before_return(state):
    module = ast.parse(SOURCE.read_text())
    fn = next(n for n in module.body if isinstance(n, ast.AsyncFunctionDef)
              and n.name == "execute_stage")
    fn.decorator_list = []
    calls = []
    version = [4]
    def core_call(method, url, payload):
        calls.append(("core", url, payload))
        if url.endswith("/events"):
            assert payload["expected_version"] == version[0]
            version[0] += 1
            return {"version": version[0], "sequence": 7}
        if url.endswith("/command"):
            assert payload["expected_version"] == version[0]
            version[0] += 1
            return {"version": version[0], "status": "BLOCKED"}
        raise AssertionError("unexpected Core URL")
    def post_json(origin, path, payload, **kwargs):
        calls.append(("external", path, payload))
        if path == "/api/evidence":
            return {"evidence_id": "demo-evidence-01"}
        if path == "/api/policy/check":
            return {"state": state, "decision": "HUMAN_APPROVAL",
                    "reason": "NO_INDEPENDENT_PROOF"}
        if path.endswith("/gates"):
            return {"ok": True}
        raise AssertionError("unexpected external path: " + path)
    ns = {
        "call": core_call, "post_json": post_json,
        "CORE": "http://core", "EVID": "http://evidence",
        "POLICY": "http://policy", "TWIN": "http://twin", "ADMIN": "inert",
        "activity": SimpleNamespace(info=lambda: SimpleNamespace(attempt=1)),
        "policy_command_for_mode": lambda mode: "SIMULATE",
    }
    exec(compile(ast.Module(body=[fn], type_ignores=[]),
                 str(SOURCE), "exec"), ns)
    result = asyncio.run(ns["execute_stage"]({
        "run_id": "demo-run-01", "version": 4, "stage": "POLICY",
        "mode": "DEMO", "scenario_id": "acme",
    }))
    assert result == {"run_id": "demo-run-01", "stage": "POLICY",
                      "status": "BLOCKED", "version": 7, "sequence": 7}
    core_events = [payload for kind, _, payload in calls
                   if kind == "core" and "event_type" in payload]
    assert [p["event_type"] for p in core_events] == ["STAGE_STARTED", "GATE_BLOCKED"]
    assert core_events[-1]["confidence"] == 0.0
    assert not any(p["event_type"] == "STAGE_COMPLETED" for p in core_events)
    commands = [payload for kind, _, payload in calls
                if kind == "core" and payload.get("command") == "BLOCK"]
    assert commands == [{"expected_version": 6,
                         "idempotency_key": "POLICY-GATE-BLOCK-demo-run-01",
                         "command": "BLOCK"}]
    assert not any(path.endswith("/checkpoint") or path.endswith("/demo-artifacts")
                   for kind, path, _ in calls if kind == "external")
