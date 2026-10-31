"""Isolated negative STAGE_STARTED Core ACK tests for #204.

AST/fake-call harness: no network, DB, Temporal service, LIVE, or executor.
Core event ACKs omit status; a valid ACK is run_id/sequence/version.
"""
import ast
import pathlib
import unittest
from unittest.mock import Mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/worker/main.py"


def load_stage(env):
    tree = ast.parse(SOURCE.read_text(), filename=str(SOURCE))
    names = ("verified_no_effect_stage_started_receipt", "_execute_stage_blocking")
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in names]
    assert {node.name for node in nodes} == set(names)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
                 str(SOURCE), "exec"), env)
    return env["_execute_stage_blocking"], env["verified_no_effect_stage_started_receipt"]


class StageStartAckFailureInjection(unittest.TestCase):
    def test_forged_start_ack_stops_before_synthetic_adapter(self):
        base = {"run_id": "RUN-OFFLINE", "sequence": 1, "version": 2}
        mutations = (
            {"run_id": "RUN-OTHER"},
            {"sequence": None}, {"sequence": True}, {"sequence": 0},
            {"sequence": "1"}, {"version": None}, {"version": True},
            {"version": 1}, {"version": 3}, {"version": 2.0},
            {"stage": "HITL"}, {"event_type": "STAGE_COMPLETED"},
            {"status": "PASS"}, {"effect_allowed": True},
            {"execution_allowed": True},
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                calls = []
                post = Mock(side_effect=AssertionError("downstream_adapter_called"))

                def fake_call(method, url, payload):
                    calls.append(payload["event_type"])
                    if payload["event_type"] != "STAGE_STARTED":
                        raise AssertionError("downstream_core_event_called")
                    return {**base, **mutation}

                env = {"call": fake_call, "post_json": post,
                       "CORE": "CORE", "TWIN": "TWIN", "EVID": "EVID",
                       "ADMIN": "offline"}
                stage, _ = load_stage(env)
                with self.assertRaisesRegex(RuntimeError,
                                            "stage_start_receipt_not_qualified"):
                    stage({"run_id": "RUN-OFFLINE", "version": 1,
                           "stage": "OBSERVE", "mode": "DEMO",
                           "scenario_id": "SCENARIO-OFFLINE"}, 1)
                self.assertEqual(calls, ["STAGE_STARTED"])
                post.assert_not_called()

    def test_valid_ack_normalized_to_no_effect_running(self):
        _, verify = load_stage({})
        result = verify({"run_id": "RUN-OFFLINE", "sequence": 1,
                         "version": 2, "idempotent": False},
                        "RUN-OFFLINE", "OBSERVE", 1)
        self.assertEqual((result["status"], result["stage"]),
                         ("RUNNING", "OBSERVE"))
        self.assertIs(result["execution_allowed"], False)
        self.assertIs(result["effect_allowed"], False)


if __name__ == "__main__":
    unittest.main()
