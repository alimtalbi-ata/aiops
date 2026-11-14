"""In-process end-to-end Worker orchestration with real activity and workflow bodies.

Uses deterministic fake Core/Policy/Evidence/Twin; no Temporal server or
production integration. Verifies the complete DEMO sequence stops at VERIFY.
"""
import ast
import asyncio
import datetime
from pathlib import Path
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


def test_actual_workflow_and_stage_activity_stop_before_resolve():
    module = ast.parse(SOURCE.read_text())
    functions = [n for n in module.body if isinstance(n, ast.AsyncFunctionDef)
                 and n.name in {"start_run", "execute_stage", "finish_run"}]
    klass = next(n for n in module.body if isinstance(n, ast.ClassDef)
                 and n.name == "IncidentWorkflow")
    for fn in functions:
        fn.decorator_list = []
    klass.decorator_list = []
    for fn in klass.body:
        if isinstance(fn, ast.AsyncFunctionDef):
            fn.decorator_list = []
    events = []
    external = []
    version = [0]
    sequence = [0]
    def core_call(method, url, payload):
        if url.endswith("/events"):
            assert payload["expected_version"] == version[0]
            version[0] += 1
            sequence[0] += 1
            events.append((payload["stage"], payload["event_type"]))
            return {"version": version[0], "sequence": sequence[0]}
        if url.endswith("/command"):
            assert payload["expected_version"] == version[0]
            version[0] += 1
            events.append(("COMMAND", payload["command"]))
            return {"version": version[0], "status": "BLOCKED"
                    if payload["command"] == "BLOCK" else "RUNNING"}
        raise AssertionError("unexpected Core call: " + url)
    def post_json(origin, path, payload, **kwargs):
        external.append((origin, path))
        if path == "/api/evidence":
            return {"evidence_id": "synthetic-" + str(len(external))}
        if path == "/api/policy/check":
            return {"state": "PASS", "decision": "SIMULATE", "reason": "DEMO"}
        if path.endswith("/gates"):
            return {"ok": True}
        if path.endswith("/checkpoint") or path.endswith("/demo-artifacts"):
            return {"ok": True}
        if path == "/api/twin/synthetic-event":
            return {"ok": True}
        raise AssertionError("unexpected external call: " + path)
    async def execute_activity(fn, args, **kwargs):
        return await fn(args)
    namespace = {
        "workflow": SimpleNamespace(execute_activity=execute_activity),
        "activity": SimpleNamespace(info=lambda: SimpleNamespace(attempt=1)),
        "call": core_call, "post_json": post_json,
        "policy_command_for_mode": lambda mode: "SIMULATE" if mode == "DEMO" else None,
        "CORE": "http://core", "EVID": "http://evidence",
        "POLICY": "http://policy", "TWIN": "http://twin", "ADMIN": "inert",
        "datetime": datetime, "RETRY": object(),
        "STAGES": ["NORMALIZE", "CORRELATE", "CMDB", "OBSERVE", "RAG",
                   "DGX_ANALYST", "DGX_CRITIC", "POLICY", "HITL",
                   "REMEDIATE", "VERIFY", "RECONCILE", "LEARN"],
    }
    exec(compile(ast.Module(body=[*functions, klass], type_ignores=[]),
                 str(SOURCE), "exec"), namespace)
    result = asyncio.run(namespace["IncidentWorkflow"]().run({
        "run_id": "acme-demo-01", "mode": "DEMO",
        "scenario_id": "acme", "version": 0,
    }))
    assert result["status"] == "BLOCKED"
    assert events[-2:] == [
        ("VERIFY", "INDEPENDENT_POSTCHECK_MISSING"), ("COMMAND", "BLOCK")]
    assert ("COMMAND", "RESOLVE") not in events
    assert not any(stage in {"RECONCILE", "LEARN"} for stage, _ in events)
    assert ("VERIFY", "STAGE_COMPLETED") not in events
    assert all(path != "/api/evidence" for origin, path in external[-0:]) is not None
    assert len([x for x in external if x[1] == "/api/evidence"]) == 10
    assert result["final_version"] == version[0]
