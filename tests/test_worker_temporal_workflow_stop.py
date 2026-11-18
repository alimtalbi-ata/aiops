"""Execute the actual IncidentWorkflow.run coroutine with a deterministic Temporal stub.

No Temporal server or external services: tests the real orchestration loop,
including stage order and the absence of finish_run after a VERIFY block.
"""
import ast
import asyncio
import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app" / "worker" / "main.py"


def _workflow_with_stub(events, *, block_stage):
    module = ast.parse(SOURCE.read_text())
    workflow_class = next(n for n in module.body if isinstance(n, ast.ClassDef)
                          and n.name == "IncidentWorkflow")
    workflow_class.decorator_list = []
    for method in workflow_class.body:
        if isinstance(method, ast.AsyncFunctionDef):
            method.decorator_list = []
    stages = [
        "NORMALIZE", "CORRELATE", "CMDB", "OBSERVE", "RAG",
        "DGX_ANALYST", "DGX_CRITIC", "POLICY", "HITL",
        "REMEDIATE", "VERIFY", "RECONCILE", "LEARN",
    ]
    async def execute_activity(activity, args, **kwargs):
        assert kwargs["start_to_close_timeout"].total_seconds() > 0
        events.append((activity.__name__, dict(args)))
        if activity.__name__ == "start_run":
            return {"version": 1}
        if activity.__name__ == "execute_stage":
            if args["stage"] == block_stage:
                return {"run_id": args["run_id"], "stage": args["stage"], "status": "BLOCKED", "version": args["version"] + 1}
            return {"run_id": args["run_id"], "stage": args["stage"], "status": "PASS", "version": args["version"] + 1}
        if activity.__name__ == "finish_run":
            return {"status": "RESOLVED", "version": args["version"] + 1}
        raise AssertionError("unknown activity")
    def start_run(): pass
    def execute_stage(): pass
    def finish_run(): pass
    namespace = {
        "workflow": SimpleNamespace(execute_activity=execute_activity),
        "start_run": start_run,
        "execute_stage": execute_stage,
        "finish_run": finish_run,
        "STAGES": stages,
        "RETRY": object(),
        "datetime": datetime,
    }
    exec(compile(ast.Module(body=[workflow_class], type_ignores=[]),
                 str(SOURCE), "exec"), namespace)
    return namespace["IncidentWorkflow"]()


def test_verify_block_stops_temporal_before_reconcile_learn_resolve():
    events = []
    workflow = _workflow_with_stub(events, block_stage="VERIFY")
    result = asyncio.run(workflow.run({
        "run_id": "demo-run-01", "mode": "DEMO", "scenario_id": "acme",
        "version": 0,
    }))
    assert result["status"] == "BLOCKED"
    assert result["run_id"] == "demo-run-01"
    assert result["final_version"] == 12
    assert events[0][0] == "start_run"
    stages = [args["stage"] for name, args in events if name == "execute_stage"]
    assert stages[-1] == "VERIFY"
    assert "RECONCILE" not in stages and "LEARN" not in stages
    assert not any(name == "finish_run" for name, _ in events)


@pytest.mark.parametrize("stage", ["POLICY", "HITL", "REMEDIATE"])
def test_earlier_block_also_stops_before_verify(stage):
    events = []
    workflow = _workflow_with_stub(events, block_stage=stage)
    result = asyncio.run(workflow.run({
        "run_id": "demo-run-01", "mode": "DEMO", "scenario_id": "acme",
        "version": 0,
    }))
    assert result["status"] == "BLOCKED"
    assert [args["stage"] for name, args in events
            if name == "execute_stage"][-1] == stage
    assert not any(name == "finish_run" for name, _ in events)
