"""Unit tests for PR #36's targeted simulation command mapping, plus static worker wiring guards.

These tests do not invoke Temporal, Core, Policy HTTP, or any production service.
"""
import ast
from pathlib import Path
import unittest

from app.shared.simulation_policy_contract import policy_command_for_mode, validate_synthetic_policy_response, validate_synthetic_gate_receipt, validate_canonical_run_binding, valid_internal_bearer


WORKER = Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


def worker_function(name):
    module = ast.parse(WORKER.read_text(encoding="utf-8"))
    return next(node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)


def contains_call(node, name):
    return any(isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
               and child.func.id == name for child in ast.walk(node))


class SimulationPolicyContractTests(unittest.TestCase):
    def test_worker_internal_bearer_requires_exact_scheme(self):
        token = "ephemeral-test-secret-keep-private"
        self.assertTrue(valid_internal_bearer("Bearer " + token, token))
        for header in (
            None, "", token, "bearer " + token, "BEARER " + token,
            "Bearer  " + token, "Bearer " + token + " ",
            "Bearer " + token + ",Bearer " + token,
            "Basic " + token, "Bearer " + token + "\\n",
            True, [], {},
        ):
            with self.subTest(header=repr(header)):
                self.assertFalse(valid_internal_bearer(header, token))
        for expected in (None, "", True, [], {}):
            with self.subTest(expected=repr(expected)):
                self.assertFalse(valid_internal_bearer("Bearer " + token, expected))

    def test_worker_start_wires_strict_internal_bearer_guard(self):
        fn = worker_function("start")
        self.assertTrue(contains_call(fn, "valid_internal_bearer"))
        self.assertFalse(any(
            isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "removeprefix"
            for node in ast.walk(fn)
        ))

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


    def test_worker_rejects_policy_pass_allow_and_malformed_dispositions(self):
        valid_reason = "synthetic only"
        bad = (
            {"state": "PASS", "decision": "ALLOW", "reason": valid_reason},
            {"state": "PASS", "decision": "HUMAN_APPROVAL", "reason": valid_reason},
            {"state": "BLOCKED", "decision": "SIMULATE", "reason": valid_reason},
            {"state": "UNKNOWN", "decision": "ALLOW", "reason": valid_reason},
            {"state": "ERROR", "decision": "HUMAN_APPROVAL", "reason": valid_reason},
            {"state": "PASS", "decision": "SIMULATE", "reason": ""},
            {"state": "PASS", "decision": "SIMULATE", "reason": "   "},
            {"state": "PASS", "decision": "SIMULATE"},
            {"state": "PASS", "decision": "SIMULATE", "reason": valid_reason,
             "effect_applied": True},
            {"state": ["PASS"], "decision": "SIMULATE", "reason": valid_reason},
            {"state": "PASS", "decision": {"value": "SIMULATE"}, "reason": valid_reason},
            None,
            [],
            "PASS",
        )
        for response in bad:
            with self.subTest(response=repr(response)), self.assertRaises(ValueError):
                validate_synthetic_policy_response(response)

    def test_worker_accepts_only_explicit_synthetic_dispositions(self):
        for state, decision in (
            ("PASS", "SIMULATE"),
            ("BLOCKED", "HUMAN_APPROVAL"),
            ("UNKNOWN", "HUMAN_APPROVAL"),
        ):
            with self.subTest(state=state, decision=decision):
                payload = {"state": state, "decision": decision, "reason": "synthetic"}
                self.assertIs(validate_synthetic_policy_response(payload), payload)

    def test_worker_validates_policy_response_before_core_gate_write(self):
        fn = worker_function("execute_stage")
        validators = [
            node for node in ast.walk(fn)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "validate_synthetic_policy_response"
        ]
        self.assertEqual(len(validators), 1)
        self.assertEqual(len(validators[0].args), 1)
        policy_call = validators[0].args[0]
        self.assertIsInstance(policy_call, ast.Call)
        self.assertIsInstance(policy_call.func, ast.Name)
        self.assertEqual(policy_call.func.id, "post_json")
        self.assertIsInstance(policy_call.args[0], ast.Name)
        self.assertEqual(policy_call.args[0].id, "POLICY")

    def test_core_gate_receipt_must_match_synthetic_run_stage_and_state(self):
        rid = "RUN-CI-DEMO-POLICY"
        policy = {"state": "PASS", "decision": "SIMULATE", "reason": "synthetic"}
        valid = {"run_id": rid, "stage": "POLICY", "state": "PASS"}
        self.assertIs(validate_synthetic_gate_receipt(valid, rid, policy), valid)
        bad = (
            None, [], True, "ok", {},
            {"run_id": rid, "stage": "POLICY", "state": "BLOCKED"},
            {"run_id": rid + "-OTHER", "stage": "POLICY", "state": "PASS"},
            {"run_id": rid, "stage": "HITL", "state": "PASS"},
            {"run_id": rid, "stage": "POLICY", "state": "PASS", "decision": "SIMULATE"},
            {"run_id": rid, "stage": "POLICY", "state": True},
        )
        for receipt in bad:
            with self.subTest(receipt=repr(receipt)), self.assertRaises(ValueError):
                validate_synthetic_gate_receipt(receipt, rid, policy)
        for invalid_run in (None, "", True):
            with self.subTest(run_id=repr(invalid_run)), self.assertRaises(ValueError):
                validate_synthetic_gate_receipt(valid, invalid_run, policy)

    def test_worker_checks_core_gate_receipt_before_any_gate_outcome(self):
        # AST wiring guard, not a Temporal runtime test.
        fn = worker_function("execute_stage")
        source = ast.unparse(fn)
        self.assertIn("validate_synthetic_gate_receipt(gate_receipt, rid, pol)", source)
        self.assertLess(source.index("validate_synthetic_gate_receipt("),
                        source.index("if pol['state'] != 'PASS'"))
        self.assertLess(source.index("validate_synthetic_gate_receipt("),
                        source.index("event_type': 'STAGE_COMPLETED'"))

    def test_worker_denial_blocks_canonical_run_before_stage_event(self):
        # AST wiring guard only: Temporal is not started by this unit test.
        fn = worker_function("execute_stage")
        denial = [node for node in ast.walk(fn) if isinstance(node, ast.If)
                  and isinstance(node.test, ast.Compare)
                  and ast.unparse(node.test) == "pol['state'] != 'PASS'"]
        self.assertEqual(len(denial), 1)
        body = denial[0].body
        command_at = next(i for i, node in enumerate(body)
                          if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == "blocked_run"
                                  for t in node.targets))
        event_at = next(i for i, node in enumerate(body)
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "blocked_event"
                                for t in node.targets))
        self.assertLess(command_at, event_at)
        self.assertIn("'command': 'BLOCK'", ast.unparse(body[command_at]))
        self.assertIn("blocked_run['version']", ast.unparse(body[event_at]))
        self.assertIn("'status': 'BLOCKED'", ast.unparse(body[-1]))


    def test_canonical_core_binding_accepts_only_matching_created_run(self):
        args = {"run_id": "RUN-DEMO-1", "mode": "DEMO",
                "scenario_id": "ACME-SAN", "version": 1}
        canonical = {"run": {"run_id": "RUN-DEMO-1", "mode": "DEMO",
                             "scenario_id": "ACME-SAN", "status": "CREATED",
                             "version": 1, "incident_id": "INC-1"}}
        self.assertIs(validate_canonical_run_binding(canonical, args), canonical["run"])
        for field, wrong in (("run_id", "RUN-LIVE-1"), ("mode", "LIVE"),
                             ("scenario_id", "OTHER"), ("status", "RESOLVED"),
                             ("version", 2)):
            altered = {"run": dict(canonical["run"], **{field: wrong})}
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_canonical_run_binding(altered, args)

    def test_canonical_core_binding_rejects_untrusted_inputs(self):
        args = {"run_id": "RUN-1", "mode": "DEMO", "scenario_id": "S1", "version": 1}
        run = {"run": dict(args, status="CREATED")}
        for invalid in (None, {}, {"run": None}, {"run": []},
                        {"run": dict(run["run"], version=True)},
                        {"run": dict(run["run"], mode="LIVE")},
                        {"run": dict(run["run"], status="RUNNING")}):
            with self.subTest(response=repr(invalid)), self.assertRaises(ValueError):
                validate_canonical_run_binding(invalid, args)
        for bad in (dict(args, version=True), dict(args, version=0),
                    dict(args, mode="DEMO ", scenario_id="S1"),
                    dict(args, run_id=""), dict(args, scenario_id=None), []):
            with self.subTest(args=repr(bad)), self.assertRaises(ValueError):
                validate_canonical_run_binding(run, bad)

    def test_canonical_core_binding_activity_retry_allows_started_only(self):
        args = {"run_id": "RUN-1", "mode": "DEMO", "scenario_id": "S1", "version": 1}
        run = {"run": dict(args, status="RUNNING", version=2)}
        self.assertIs(validate_canonical_run_binding(run, args, allow_started=True),
                      run["run"])
        with self.assertRaises(ValueError):
            validate_canonical_run_binding(run, args)
        for status in ("BLOCKED", "RESOLVED", "FAILED", "CANCELLED"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                validate_canonical_run_binding(
                    {"run": dict(run["run"], status=status)}, args,
                    allow_started=True)

    def test_worker_preflights_canonical_run_before_temporal_and_core_start(self):
        # AST wiring check only; no Temporal or Core service is started here.
        http = ast.unparse(worker_function("start"))
        self.assertLess(http.index("re.fullmatch("), http.index("get_json("))
        self.assertLess(http.index("validate_canonical_run_binding("),
                        http.index("Client.connect("))
        activity_start = ast.unparse(worker_function("start_run"))
        self.assertLess(activity_start.index("validate_canonical_run_binding("),
                        activity_start.index("return call("))
        self.assertIn("allow_started=True", activity_start)


if __name__ == "__main__":
    unittest.main()
