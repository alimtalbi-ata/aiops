"""Real ephemeral Policy HTTP regression: no TestClient/mocks, no LIVE side effects.

CI starts the existing Policy FastAPI service on 127.0.0.1:1813. This
checks HTTP decisions, NOT Temporal/HITL/Evidence integration or deployment.
"""
import unittest

import requests

BASE = "http://127.0.0.1:1813"


def request_body(**changes):
    value = {
        "mode": "DEMO",
        "command": "OBSERVE",
        "severity": "P2",
        "confidence": 0.99,
        "evidence_count": 2,
        "critic_validated": True,
        "redundancy_ok": True,
        "evidence_fresh": True,
        "preconditions_verified": True,
        "fencing_verified": True,
        "human_approved": False,
    }
    value.update(changes)
    return value


class RealPolicyHTTPIntegration(unittest.TestCase):
    def check(self, **changes):
        return requests.post(BASE + "/api/policy/check", json=request_body(**changes),
                             timeout=3, allow_redirects=False)

    def test_health_is_actual_policy_service(self):
        response = requests.get(BASE + "/health", timeout=3, allow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["component"], "policy")
        self.assertIs(response.json()["fail_closed"], True)

    def test_demo_decision_is_simulate_even_for_mutation_named_command(self):
        for command in ("OBSERVE", "REMEDIATE", "EXECUTE"):
            with self.subTest(command=command):
                response = self.check(mode="DEMO", command=command,
                                      human_approved=True)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["state"], "PASS")
                self.assertEqual(response.json()["decision"], "SIMULATE")
                self.assertNotEqual(response.json()["decision"], "ALLOW")

    def test_demo_without_evidence_is_unknown_not_fake_simulation_pass(self):
        response = self.check(mode="DEMO", evidence_count=0)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()["state"], response.json()["decision"]),
                         ("UNKNOWN", "HUMAN_APPROVAL"))

    def test_live_p1_escalates_even_with_missing_evidence(self):
        response = self.check(mode="LIVE", severity="P1", evidence_count=0,
                              command="REMEDIATE", human_approved=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()["state"], response.json()["decision"]),
                         ("BLOCKED", "ESCALATE"))

    def test_live_effect_denied_even_with_caller_controlled_approval(self):
        for command in ("EXECUTE", "RESOLVE", "REMEDIATE", "CANCEL"):
            with self.subTest(command=command):
                response = self.check(mode="LIVE", command=command,
                                      human_approved=True)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual((response.json()["state"], response.json()["decision"]),
                                 ("BLOCKED", "HUMAN_APPROVAL"))
                self.assertIn("one-use HITL binding", response.json()["reason"])

    def test_live_read_only_requires_safety_fences(self):
        allowed = self.check(mode="LIVE", command="OBSERVE")
        self.assertEqual(allowed.status_code, 200, allowed.text)
        self.assertEqual((allowed.json()["state"], allowed.json()["decision"]),
                         ("PASS", "ALLOW"))
        denied = self.check(mode="LIVE", command="OBSERVE",
                            fencing_verified=False)
        self.assertEqual(denied.status_code, 200, denied.text)
        self.assertEqual((denied.json()["state"], denied.json()["decision"]),
                         ("BLOCKED", "HUMAN_APPROVAL"))

    def test_invalid_mode_or_free_form_command_rejected_at_http_boundary(self):
        for changes in ({"mode": "LIVE_SIMULATED"}, {"command": "SHELL"},
                        {"command": "RUN_SCRIPT"}, {"mode": "live"}):
            with self.subTest(changes=changes):
                response = self.check(**changes)
                self.assertEqual(response.status_code, 422, response.text)

    def test_missing_critic_validation_rejected_at_http_boundary(self):
        payload = request_body()
        del payload["critic_validated"]
        response = requests.post(BASE + "/api/policy/check", json=payload,
                                 timeout=3, allow_redirects=False)
        self.assertEqual(response.status_code, 422, response.text)


    def test_real_http_verdicts_preserve_strict_non_authorizing_contract(self):
        # Real Policy service on the CI loopback; not Core, OIDC or Temporal.
        for mode, command, evidence_count in (
            ("DEMO", "REMEDIATE", 2),
            ("REPLAY", "EXECUTE", 0),
            ("STORY", "CANCEL", 2),
            ("LIVE", "OBSERVE", 2),
            ("LIVE", "REMEDIATE", 2),
        ):
            with self.subTest(mode=mode, command=command, evidence_count=evidence_count):
                response = self.check(mode=mode, command=command,
                                      evidence_count=evidence_count,
                                      human_approved=True)
                self.assertEqual(response.status_code, 200, response.text)
                # Existing Core cross-check rejects any extra HTTP fields.
                self.assertEqual(set(response.json()), {"state", "decision", "reason"})
                self.assertNotIn(response.json()["decision"], ("EXECUTE", "REMEDIATE"))


if __name__ == "__main__":
    unittest.main()
