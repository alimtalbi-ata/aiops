import unittest
from types import SimpleNamespace
from worker.fs147_policy_adapter import check_fs147_policy


class PolicyAdapterTests(unittest.TestCase):
    def setUp(self):
        self.req = SimpleNamespace(mode="DEMO", ticket_id=147, tenant_id="t", actor_id="a", incident_id="i", run_id="r")
        self.obs = {"evidence_id": "e"}
        self.analysis = {"evidence_id": "e"}
        self.critic = {"evidence_id": "e", "state": "PASS"}

    def call(self, post):
        return check_fs147_policy(self.req, self.obs, self.analysis, self.critic, post_check=post)

    def test_response_bound_without_hitl(self):
        seen = []
        result = self.call(lambda p: (seen.append(p), {"state": "PASS", "decision": "SIMULATE"})[1])
        self.assertEqual((result["run_id"], result["evidence_id"]), ("r", "e"))
        self.assertFalse(seen[0]["human_approved"])
        self.assertEqual(seen[0]["command"], "OBSERVE")
        self.assertFalse(seen[0]["preconditions_verified"])

    def test_refusal_preserved(self):
        self.assertEqual(self.call(lambda p: {"state": "BLOCKED", "decision": "HUMAN_APPROVAL"})["state"], "BLOCKED")

    def test_mismatched_evidence_stops_before_policy(self):
        self.analysis["evidence_id"] = "wrong"
        with self.assertRaises(ValueError):
            self.call(lambda p: self.fail("Policy must not be called"))

    def test_failed_critic_stops_before_policy(self):
        self.critic["state"] = "BLOCKED"
        with self.assertRaises(ValueError):
            self.call(lambda p: self.fail("Policy must not be called"))

    def test_live_stops_before_policy(self):
        self.req.mode = "LIVE"
        with self.assertRaises(ValueError):
            self.call(lambda p: self.fail("Policy must not be called"))

    def test_invalid_policy_response_rejected(self):
        with self.assertRaises(ValueError):
            self.call(lambda p: {"state": "RESOLVED", "decision": "ALLOW"})

    def test_transport_error_propagates(self):
        def unavailable(_):
            raise ConnectionError("policy unavailable")
        with self.assertRaises(ConnectionError):
            self.call(unavailable)


if __name__ == "__main__":
    unittest.main()
