"""Contract tests for the current Core/Temporal synthetic-mode and Policy boundary."""
import ast
from pathlib import Path
import unittest

from app.shared.simulation_policy_contract import policy_command_for_mode

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "app" / "worker" / "main.py"
WORKFLOW = ROOT / "app" / "worker" / "workflow.py"
CORE = ROOT / "app" / "core" / "main.py"


def parse(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def function(path, name):
    module = parse(path)
    return next(node for node in module.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == name)


def contains_call(node, name):
    return any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
               and child.func.id == name for child in ast.walk(node))


def dict_values(node):
    return {
        key.value: value
        for key, value in zip(node.keys, node.values)
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


class SimulationPolicyContractTests(unittest.TestCase):
    def test_synthetic_modes_request_observation_not_execution(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                self.assertEqual(policy_command_for_mode(mode), "OBSERVE")

    def test_live_mode_keeps_strict_effect_policy_path(self):
        self.assertEqual(policy_command_for_mode("LIVE"), "EXECUTE")

    def test_unknown_modes_rejected(self):
        for mode in ("", "demo", "SIMULATION", "UNKNOWN", None, {}, [], 0, True):
            with self.subTest(mode=repr(mode)), self.assertRaises(ValueError):
                policy_command_for_mode(mode)

    def test_core_run_contract_rejects_unknown_modes_before_persistence(self):
        module = parse(CORE)
        run_in = next(node for node in module.body
                      if isinstance(node, ast.ClassDef) and node.name == "RunIn")
        mode_field = next(node for node in run_in.body
                          if isinstance(node, ast.AnnAssign)
                          and isinstance(node.target, ast.Name)
                          and node.target.id == "mode")
        field_call = mode_field.value
        self.assertIsInstance(field_call, ast.Call)
        pattern = next(kw.value for kw in field_call.keywords if kw.arg == "pattern")
        self.assertEqual(pattern.value, "^(LIVE|DEMO|REPLAY|STORY)$")

    def test_temporal_workflow_propagates_canonical_mode_to_every_stage(self):
        run = function(WORKFLOW, "run")
        calls = [node for node in ast.walk(run)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and node.func.attr == "execute_activity"
                 and node.args and isinstance(node.args[0], ast.Constant)
                 and node.args[0].value == "execute_stage"]
        self.assertEqual(len(calls), 1)
        payload = calls[0].args[1]
        self.assertIsInstance(payload, ast.Dict)
        values = dict_values(payload)
        self.assertIsInstance(values["mode"], ast.Subscript)
        self.assertIsInstance(values["mode"].value, ast.Name)
        self.assertEqual(values["mode"].value.id, "args")
        self.assertEqual(values["mode"].slice.value, "mode")

    def test_synthetic_hitl_stage_is_explicitly_skipped_without_execution(self):
        stage = function(WORKER, "_execute_stage_blocking")
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("HITL_SIMULATION_SKIPPED", source)
        self.assertIn("'execution_allowed':False", source.replace(" ", ""))
        self.assertIn("'synthetic':True", source.replace(" ", ""))
        self.assertTrue(contains_call(stage, "call"))

    def test_policy_request_carries_mode_and_keeps_human_approval_false(self):
        stage = function(WORKER, "_execute_stage_blocking")
        calls = [node for node in ast.walk(stage)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "post_json"
                 and node.args and isinstance(node.args[0], ast.Name)
                 and node.args[0].id == "POLICY"
                 and len(node.args) >= 3
                 and isinstance(node.args[2], ast.Name)
                 and node.args[2].id == "policy_input"]
        self.assertEqual(len(calls), 1)
        assignment = next(node for node in ast.walk(stage)
                          if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "policy_input"
                                  for t in node.targets)
                          and isinstance(node.value, ast.Dict))
        values = dict_values(assignment.value)
        self.assertIsInstance(values["mode"], ast.Name)
        self.assertEqual(values["mode"].id, "mode")
        self.assertEqual(values["command"].value, "EXECUTE")
        self.assertIs(values["human_approved"].value, False)
        self.assertIs(values["fencing_verified"].value, False)


if __name__ == "__main__":
    unittest.main()
