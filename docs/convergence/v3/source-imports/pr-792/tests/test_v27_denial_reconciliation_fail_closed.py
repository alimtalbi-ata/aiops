"""V2.7 rejected-Critic denial reconciliation: fail-closed unit contracts.

Tests extract only the pure orchestration function from Worker source, so no
Temporal, HTTP services, Docker, database, or LIVE effect is required.
This does NOT qualify transactionality, concurrency or the migration.
"""
import ast
import pathlib
import unittest
from unittest.mock import Mock

SOURCE = pathlib.Path(__file__).resolve().parents[1] / "app" / "worker" / "main.py"


def load_reconciler():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and
                 n.name == "reconcile_denial_batch"]
    if len(functions) != 1:
        raise AssertionError("Expected exactly one reconciler implementation")
    module = ast.Module(body=functions, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {}
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["reconcile_denial_batch"]


class DenialReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.fn = load_reconciler()
        self.item = {
            "run_id": "RUN-SYNTHETIC-1", "critique_id": "CRIT-1",
            "analysis_id": "ANA-1", "evidence_ids": ["EVD-1"],
            "policy_input": {"command": "EXECUTE", "critic_validated": False},
        }
        self.ns = self.fn.__globals__
        self.posts = []
        self.ns["CORE"] = "http://core:810"
        self.ns["POLICY"] = "http://policy:813"
        self.ns["ADMIN"] = "synthetic-unit-test-token"
        self.ns["log"] = Mock()
        self.ns["get_json"] = Mock(return_value={"items": [self.item]})
        self.policy = {"state": "BLOCKED", "decision": "HUMAN_APPROVAL"}
        self.ns["post_json"] = self.fake_post

    def fake_post(self, base, path, payload, **kwargs):
        self.posts.append((base, path, payload))
        if base == self.ns["POLICY"]:
            return self.policy
        if path.endswith("/policy-record"):
            return {"policy_decision_id": "POL-1"}
        return {"status": "RECONCILED"}

    def test_reconciles_only_verified_denial(self):
        self.fn()
        self.assertEqual([p for _, p, _ in self.posts], [
            "/api/policy/check",
            "/api/runs/RUN-SYNTHETIC-1/policy-record",
            "/api/runs/RUN-SYNTHETIC-1/denial-intent/CRIT-1/reconciled",
        ])
        self.assertEqual(self.posts[-1][2], {"policy_decision_id": "POL-1"})
        self.assertFalse(any("command" in path or "remediate" in path.lower()
                             for _, path, _ in self.posts))

    def test_rejects_policy_pass_without_side_effect(self):
        self.policy = {"state": "PASS", "decision": "AUTO_REMEDIATE"}
        self.fn()
        self.assertEqual(len(self.posts), 1)
        self.ns["log"].warning.assert_called_once()

    def test_rejects_unexpected_block_decision(self):
        self.policy = {"state": "BLOCKED", "decision": "AUTO_REMEDIATE"}
        self.fn()
        self.assertEqual(len(self.posts), 1)

    def test_policy_outage_does_not_ack(self):
        def unavailable(base, path, payload, **kwargs):
            self.posts.append((base, path, payload))
            raise ConnectionError("synthetic Policy outage")
        self.ns["post_json"] = unavailable
        self.fn()
        self.assertEqual(len(self.posts), 1)
        self.ns["log"].warning.assert_called_once()

    def test_core_write_outage_does_not_ack(self):
        def fail_write(base, path, payload, **kwargs):
            self.posts.append((base, path, payload))
            if path.endswith("/policy-record"):
                raise ConnectionError("synthetic Core outage")
            return self.policy
        self.ns["post_json"] = fail_write
        self.fn()
        self.assertEqual(len(self.posts), 2)
        self.ns["log"].warning.assert_called_once()

    def test_ack_outage_still_fails_closed(self):
        def fail_ack(base, path, payload, **kwargs):
            self.posts.append((base, path, payload))
            if path.endswith("/reconciled"):
                raise ConnectionError("synthetic ACK outage")
            if path.endswith("/policy-record"):
                return {"policy_decision_id": "POL-1"}
            return self.policy
        self.ns["post_json"] = fail_ack
        self.fn()
        self.assertEqual(len(self.posts), 3)
        self.ns["log"].warning.assert_called_once()


if __name__ == "__main__":
    unittest.main()
