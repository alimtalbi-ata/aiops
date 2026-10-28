"""Unit tests for PR #36's targeted simulation command mapping, plus static worker wiring guards.

These tests do not invoke Temporal, Core, Policy HTTP, or any production service.
"""
import ast
from pathlib import Path
import unittest

from app.shared.simulation_policy_contract import policy_command_for_mode


WORKER = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


def worker_function(name):
    module = ast.parse(WORKER.read_text(encoding="utf-8"))
    return next(node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)


def contains_call(node, name):
    return any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
               and child.func.id == name for child in ast.walk(node))


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

    def test_worker_validates_mode_before_first_stage_event(self):
        fn = worker_function("execute_stage")
        guard = next(i for i, node in enumerate(fn.body)
                     if isinstance(node, ast.Assign) and any(
                         isinstance(t, ast.Name) and t.id == "policy_command" for t in node.targets))
        first_event = next(i for i, node in enumerate(fn.body)
                           if isinstance(node, ast.Assign) and any(
                               isinstance(t, ast.Name) and t.id == "started" for t in node.targets))
        self.assertLess(guard, first_event)
        self.assertTrue(contains_call(fn.body[guard], "policy_command_for_mode"))

    def test_policy_request_uses_mapped_command(self):
        fn = worker_function("execute_stage")
        policy_calls = [node for node in ast.walk(fn) if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name) and node.func.id == "post_json"
                        and node.args and isinstance(node.args[0], ast.Name)
                        and node.args[0].id == "POLICY"]
        self.assertEqual(len(policy_calls), 1)
        request = policy_calls[0].args[2]
        self.assertIsInstance(request, ast.Dict)
        command_values = [value for key, value in zip(request.keys, request.values)
                          if isinstance(key, ast.Constant) and key.value == "command"]
        self.assertEqual(len(command_values), 1)
        self.assertIsInstance(command_values[0], ast.Name)
        self.assertEqual(command_values[0].id, "policy_command")

    def test_http_start_validates_mode_before_temporal_connection(self):
        fn = worker_function("start")
        validation = next(i for i, node in enumerate(fn.body)
                          if contains_call(node, "policy_command_for_mode"))
        connection = next(i for i, node in enumerate(fn.body)
                          if contains_call(node, "Client") or any(
                              isinstance(x, ast.Attribute) and x.attr == "connect"
                              for x in ast.walk(node)))
        self.assertLess(validation, connection)


if __name__ == "__main__":
    unittest.main()
