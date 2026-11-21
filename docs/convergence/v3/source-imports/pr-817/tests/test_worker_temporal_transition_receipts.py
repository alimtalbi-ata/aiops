"""Temporal loop rejects unbound, stale or out-of-order stage receipts."""
import ast
import asyncio
import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


def start_run(): pass
def execute_stage(): pass
def finish_run(): pass


def workflow_for(result_factory, events):
    module = ast.parse(SOURCE.read_text())
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef)
               and n.name == "IncidentWorkflow")
    cls.decorator_list = []
    for fn in cls.body:
        if isinstance(fn, ast.AsyncFunctionDef):
            fn.decorator_list = []
    async def execute_activity(activity, args, **kwargs):
        events.append((activity.__name__, dict(args)))
        if activity.__name__ == "start_run":
            return {"version": 4}
        if activity.__name__ == "execute_stage":
            return result_factory(args)
        if activity.__name__ == "finish_run":
            return {"status": "RESOLVED", "version": args["version"] + 1}
        raise AssertionError(activity.__name__)
    namespace = {
        "workflow": SimpleNamespace(execute_activity=execute_activity),
        "start_run": start_run, "execute_stage": execute_stage,
        "finish_run": finish_run, "STAGES": ["POLICY", "HITL", "REMEDIATE", "VERIFY"],
        "RETRY": object(), "datetime": datetime,
    }
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["IncidentWorkflow"]()


@pytest.mark.parametrize("mutate", [
    lambda a: {"run_id": "foreign-run", "stage": a["stage"], "status": "PASS", "version": a["version"] + 1},
    lambda a: {"run_id": a["run_id"], "stage": "WRONG", "status": "PASS", "version": a["version"] + 1},
    lambda a: {"run_id": a["run_id"], "stage": a["stage"], "status": "UNKNOWN", "version": a["version"] + 1},
    lambda a: {"run_id": a["run_id"], "stage": a["stage"], "status": "PASS", "version": a["version"]},
    lambda a: {"run_id": a["run_id"], "stage": a["stage"], "status": "PASS", "version": True},
])
def test_workflow_fails_closed_on_unqualified_stage_transition(mutate):
    events = []
    workflow = workflow_for(mutate, events)
    with pytest.raises(ValueError, match="unqualified_stage_transition_receipt"):
        asyncio.run(workflow.run({"run_id": "demo-run", "mode": "DEMO",
                                  "scenario_id": "acme", "version": 0}))
    assert [name for name, _ in events] == ["start_run", "execute_stage"]


def test_workflow_accepts_only_monotonic_bound_transitions_then_terminal_resolve():
    events = []
    def passing(args):
        return {"run_id": args["run_id"], "stage": args["stage"],
                "status": "PASS", "version": args["version"] + 2}
    workflow = workflow_for(passing, events)
    result = asyncio.run(workflow.run({"run_id": "demo-run", "mode": "DEMO",
                                       "scenario_id": "acme", "version": 0}))
    assert result == {"run_id": "demo-run", "final_version": 13, "status": "RESOLVED"}
    calls = [args for name, args in events if name == "execute_stage"]
    assert [x["stage"] for x in calls] == ["POLICY", "HITL", "REMEDIATE", "VERIFY"]
    assert [x["version"] for x in calls] == [4, 6, 8, 10]
    assert events[-1][0] == "finish_run"


def test_workflow_stops_at_bound_blocked_stage_without_finish():
    events = []
    def blocked(args):
        return {"run_id": args["run_id"], "stage": args["stage"],
                "status": "BLOCKED", "version": args["version"] + 1}
    workflow = workflow_for(blocked, events)
    result = asyncio.run(workflow.run({"run_id": "demo-run", "mode": "DEMO",
                                       "scenario_id": "acme", "version": 0}))
    assert result["status"] == "BLOCKED"
    assert result["blocked_stage"] == "POLICY"
    assert events[-1][0] == "execute_stage"
    assert not any(name == "finish_run" for name, _ in events)

def test_workflow_rejects_unqualified_terminal_resolution():
    events = []
    module = ast.parse(SOURCE.read_text())
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef)
               and n.name == "IncidentWorkflow")
    cls.decorator_list = []
    for fn in cls.body:
        if isinstance(fn, ast.AsyncFunctionDef):
            fn.decorator_list = []
    async def execute_activity(activity, args, **kwargs):
        events.append(activity.__name__)
        if activity.__name__ == "start_run":
            return {"version": 0}
        if activity.__name__ == "execute_stage":
            return {"run_id": args["run_id"], "stage": args["stage"],
                    "status": "PASS", "version": args["version"] + 1}
        return {"status": "UNKNOWN", "version": args["version"] + 1}
    namespace = {"workflow": SimpleNamespace(execute_activity=execute_activity),
                 "start_run": start_run, "execute_stage": execute_stage,
                 "finish_run": finish_run, "STAGES": ["VERIFY"],
                 "RETRY": object(), "datetime": datetime}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE), "exec"), namespace)
    with pytest.raises(ValueError, match="unqualified_terminal_transition_receipt"):
        asyncio.run(namespace["IncidentWorkflow"]().run({
            "run_id": "demo-run", "mode": "DEMO", "scenario_id": "acme", "version": 0}))
    assert events == ["start_run", "execute_stage", "finish_run"]


def test_workflow_rejects_boolean_start_version():
    events = []
    module = ast.parse(SOURCE.read_text())
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef)
               and n.name == "IncidentWorkflow")
    cls.decorator_list = []
    for fn in cls.body:
        if isinstance(fn, ast.AsyncFunctionDef):
            fn.decorator_list = []
    async def execute_activity(activity, args, **kwargs):
        events.append(activity.__name__)
        return {"version": True}
    namespace = {"workflow": SimpleNamespace(execute_activity=execute_activity),
                 "start_run": start_run, "execute_stage": execute_stage,
                 "finish_run": finish_run, "STAGES": ["VERIFY"],
                 "RETRY": object(), "datetime": datetime}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), str(SOURCE), "exec"), namespace)
    with pytest.raises(ValueError, match="unqualified_start_run_version"):
        asyncio.run(namespace["IncidentWorkflow"]().run({
            "run_id": "demo-run", "mode": "DEMO", "scenario_id": "acme", "version": 0}))
    assert events == ["start_run"]


@pytest.mark.parametrize("blocked_stage", ["DGX_CRITIC", "POLICY", "HITL", "REMEDIATE", "VERIFY"])
@pytest.mark.parametrize("status", ["BLOCKED", "FAIL"])
def test_no_downstream_action_after_denied_or_failed_stage(blocked_stage, status):
    events = []
    stages = ["DGX_CRITIC", "POLICY", "HITL", "REMEDIATE", "VERIFY"]
    def result(args):
        return {"run_id": args["run_id"], "stage": args["stage"],
                "status": status if args["stage"] == blocked_stage else "PASS",
                "version": args["version"] + 1}
    instance = workflow_for(result, events)
    instance.run.__func__.__globals__["STAGES"] = stages
    args = {"run_id": "demo-run", "mode": "DEMO", "scenario_id": "acme", "version": 0}
    if status == "FAIL":
        with pytest.raises(ValueError, match="unqualified_stage_transition_receipt"):
            asyncio.run(instance.run(args))
    else:
        assert asyncio.run(instance.run(args))["blocked_stage"] == blocked_stage
    assert [a["stage"] for name,a in events if name == "execute_stage"] == stages[:stages.index(blocked_stage)+1]
    assert not any(name == "finish_run" for name,_ in events)
