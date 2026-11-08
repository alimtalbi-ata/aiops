"""Execute Worker activity/workflow bodies with offline service doubles.

AST extraction follows test_simulation_policy_contract's source selection, but
executes the selected bodies. SDK decorators, server startup and credentials are
excluded. This is NOT a Temporal history replay or a durable Core dedup test.
Run: python -m unittest discover -s tests -p 'test_worker_pipeline_safety.py' -v
"""
import ast
import datetime
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

from app.shared.simulation_policy_contract import policy_command_for_mode


SOURCE = Path(__file__).resolve().parents[1] / "app/worker/main.py"


def load_bodies():
    names = {"start_run", "execute_stage", "finish_run", "IncidentWorkflow"}
    tree = ast.parse(SOURCE.read_text())
    tree.body = [node for node in tree.body
                 if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef))
                 and node.name in names]
    if {node.name for node in tree.body} != names:
        raise AssertionError("Worker entrypoints changed; review test harness")
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.ClassDef)):
            node.decorator_list = []
    scope = dict(datetime=datetime, policy_command_for_mode=policy_command_for_mode,
                 CORE="core", EVID="evidence", POLICY="policy", TWIN="twin",
                 ADMIN="offline-fixture", RETRY=object(),
                 activity=SimpleNamespace(info=lambda: SimpleNamespace(attempt=1)),
                 STAGES=["DGX_CRITIC", "POLICY", "HITL", "REMEDIATE", "VERIFY"],
                 workflow=SimpleNamespace(execute_activity=AsyncMock()),
                 call=Mock(), post_json=Mock())
    exec(compile(tree, str(SOURCE), "exec"), scope)
    return scope


class WorkerPipelineSafetyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.worker = load_bodies()
        self.args = dict(run_id="offline-run", version=1, stage="POLICY",
                         mode="DEMO", scenario_id="offline-scenario")

    async def test_unknown_mode_has_no_service_effects(self):
        for mode in (None, "", "demo", "UNKNOWN"):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                await self.worker["execute_stage"](dict(self.args, mode=mode))
        self.worker["call"].assert_not_called()
        self.worker["post_json"].assert_not_called()

    async def test_live_stages_never_write_evidence_or_twin_or_call_policy(self):
        for stage in ("OBSERVE", "DGX_ANALYST", "DGX_CRITIC", "POLICY",
                      "HITL", "REMEDIATE", "VERIFY"):
            with self.subTest(stage=stage):
                self.worker["call"].reset_mock()
                self.worker["call"].side_effect = [
                    {"version": 2}, {"version": 3, "sequence": 2}, {"version": 4}]
                result = await self.worker["execute_stage"](
                    dict(self.args, stage=stage, mode="LIVE"))
                self.assertEqual(result["status"], "BLOCKED")
                self.worker["post_json"].assert_not_called()
                payloads = [call.args[2] for call in self.worker["call"].call_args_list]
                self.assertEqual(payloads[-1]["command"], "BLOCK")
                self.assertFalse(payloads[1]["payload"]["synthetic_evidence_created"])

    async def test_policy_denial_does_not_complete_or_checkpoint_stage(self):
        for state in ("BLOCKED", "UNKNOWN", "FAIL"):
            with self.subTest(state=state):
                worker = load_bodies()
                worker["call"].side_effect = [{"version": 2}, {"version": 3, "status": "BLOCKED"}]
                worker["post_json"].side_effect = [
                    {"evidence_id": "offline-evidence"},
                    {"state": state, "decision": "DENY", "reason": "offline refusal"}, {}]
                result = await worker["execute_stage"](self.args)
                self.assertEqual(result["status"], "BLOCKED")
                events = [call.args[2] for call in worker["call"].call_args_list]
                self.assertEqual([event["event_type"] for event in events],
                                 ["STAGE_STARTED", "GATE_BLOCKED"])
                self.assertEqual(events[-1]["evidence_ids"], ["offline-evidence"])
                self.assertEqual([call.args[1] for call in worker["post_json"].call_args_list],
                                 ["/api/evidence", "/api/policy/check", "/api/runs/offline-run/gates"])

    async def test_activity_retry_preserves_event_and_command_keys(self):
        # Stable keys are a prerequisite, not proof that Core deduplicates writes.
        worker = self.worker
        worker["call"].side_effect = None
        worker["call"].return_value = {"version": 2, "sequence": 1}
        await worker["start_run"](self.args)
        await worker["start_run"](self.args)
        self.assertEqual(worker["call"].call_args_list[0], worker["call"].call_args_list[1])
        worker["call"].reset_mock()
        for attempt in (1, 2):
            worker["activity"].info = lambda: SimpleNamespace(attempt=attempt)
            await worker["execute_stage"](dict(self.args, mode="LIVE"))
        payloads = [call.args[2] for call in worker["call"].call_args_list]
        for first, retry in zip(payloads[:3], payloads[3:]):
            key = "event_key" if "event_key" in first else "idempotency_key"
            self.assertEqual(first[key], retry[key])
        self.assertEqual(payloads[0]["payload"]["attempt"], 1)
        self.assertEqual(payloads[3]["payload"]["attempt"], 2)
        worker["post_json"].assert_not_called()

    async def test_blocked_workflow_never_reaches_hitl_remediation_or_resolve(self):
        for blocked_stage in ("DGX_CRITIC", "POLICY"):
            with self.subTest(stage=blocked_stage):
                worker = load_bodies()
                seen = []

                async def execute(fn, args, **options):
                    seen.append((fn.__name__, args.copy()))
                    status = "BLOCKED" if args.get("stage") == blocked_stage else "PASS"
                    return {"version": args["version"] + 1, "status": status}

                worker["workflow"].execute_activity.side_effect = execute
                result = await worker["IncidentWorkflow"]().run(self.args)
                self.assertEqual(result["status"], "BLOCKED")
                stages = [args["stage"] for name, args in seen if name == "execute_stage"]
                self.assertEqual(stages[-1], blocked_stage)
                self.assertFalse(set(stages) & {"HITL", "REMEDIATE", "VERIFY"})
                self.assertNotIn("finish_run", [name for name, _ in seen])


if __name__ == "__main__":
    unittest.main()
