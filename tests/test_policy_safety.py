import unittest

from fastapi.testclient import TestClient

from app.policy.main import Decision, app, evaluate


def decision(**overrides):
    values = {
        "mode": "LIVE",
        "command": "EXECUTE",
        "severity": "P2",
        "confidence": 0.99,
        "evidence_count": 2,
        "critic_validated": True,
        "redundancy_ok": True,
        "evidence_fresh": True,
        "preconditions_verified": True,
        "fencing_verified": True,
        "human_approved": True,
    }
    values.update(overrides)
    return Decision(**values)


class PolicySafetyTests(unittest.TestCase):
    def test_p1_is_always_escalated_even_with_all_proofs(self):
        result = evaluate(decision(severity="P1"))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_p1_without_evidence_still_escalates(self):
        result = evaluate(decision(severity="P1", evidence_count=0))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertEqual(result["decision"], "ESCALATE")

    def test_missing_evidence_is_unknown_for_non_p1(self):
        result = evaluate(decision(evidence_count=0))
        self.assertEqual(result["state"], "UNKNOWN")
        self.assertEqual(result["decision"], "HUMAN_APPROVAL")

    def test_live_missing_fencing_is_blocked(self):
        result = evaluate(decision(fencing_verified=False))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("fencing", result["reason"])

    def test_live_effect_without_human_approval_is_blocked(self):
        result = evaluate(decision(human_approved=False))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("human approval", result["reason"])

    def test_live_p2_observe_with_all_required_proofs_can_pass_policy(self):
        result = evaluate(decision(command="OBSERVE"))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "ALLOW")

    def test_live_effect_with_boolean_approval_cannot_pass(self):
        for command in ("EXECUTE", "RESOLVE", "REMEDIATE", "CANCEL"):
            with self.subTest(command=command):
                result = evaluate(decision(command=command, human_approved=True))
                self.assertEqual(result["state"], "BLOCKED")
                self.assertEqual(result["decision"], "HUMAN_APPROVAL")
                self.assertIn("one-use HITL binding", result["reason"])

    def test_live_cancel_without_human_approval_is_blocked(self):
        result = evaluate(decision(command="CANCEL", human_approved=False))
        self.assertEqual(result["state"], "BLOCKED")
        self.assertIn("human approval", result["reason"])

    def test_live_enrich_with_all_required_proofs_can_pass_policy(self):
        result = evaluate(decision(command="ENRICH", human_approved=False))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "ALLOW")

    def test_other_synthetic_modes_never_allow_live_effect(self):
        for mode in ("REPLAY", "STORY"):
            with self.subTest(mode=mode):
                result = evaluate(decision(mode=mode, command="REMEDIATE"))
                self.assertEqual(result["decision"], "SIMULATE")

    def test_demo_is_simulation_only(self):
        result = evaluate(decision(mode="DEMO", human_approved=False))
        self.assertEqual(result["state"], "PASS")
        self.assertEqual(result["decision"], "SIMULATE")


    def test_http_live_mutation_denies_forged_boolean(self):
        # Exercise the actual FastAPI/Pydantic boundary, not only evaluate().
        with TestClient(app) as client:
            for command in ("EXECUTE", "RESOLVE", "REMEDIATE", "CANCEL"):
                with self.subTest(command=command):
                    payload = decision(command=command, human_approved=True).model_dump()
                    response = client.post("/api/policy/check", json=payload)
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    self.assertEqual(result["state"], "BLOCKED")
                    self.assertEqual(result["decision"], "HUMAN_APPROVAL")
                    self.assertIn("one-use HITL binding", result["reason"])

    def test_http_invalid_mode_and_command_are_rejected(self):
        with TestClient(app) as client:
            for override in ({"mode": "LIVE_SIMULATED"}, {"mode": "live"},
                             {"command": "SHELL"}, {"command": "APPROVE"}):
                with self.subTest(override=override):
                    payload = decision().model_dump()
                    payload.update(override)
                    response = client.post("/api/policy/check", json=payload)
                    self.assertEqual(response.status_code, 422)

    def test_http_synthetic_modes_never_claim_live_allow(self):
        with TestClient(app) as client:
            for mode in ("DEMO", "REPLAY", "STORY"):
                with self.subTest(mode=mode):
                    payload = decision(mode=mode, command="REMEDIATE").model_dump()
                    response = client.post("/api/policy/check", json=payload)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["decision"], "SIMULATE")


    def test_all_synthetic_policy_paths_are_explicitly_no_effect(self):
        # Cross disposition, evidence and caller-controlled approval booleans.
        # These are offline contract tests, not OIDC or Temporal attestation.
        for mode in ("DEMO", "REPLAY", "STORY"):
            for command in ("OBSERVE", "EXECUTE", "REMEDIATE", "CANCEL"):
                for evidence_count in (0, 2):
                    for human_approved in (False, True):
                        with self.subTest(mode=mode, command=command,
                                          evidence_count=evidence_count,
                                          human_approved=human_approved):
                            result = evaluate(decision(mode=mode, command=command,
                                evidence_count=evidence_count, human_approved=human_approved))
                            self.assertIs(result["execution_allowed"], False)
                            self.assertIs(result["effect_allowed"], False)
                            self.assertIn(result["decision"], ("SIMULATE", "HUMAN_APPROVAL"))
                            self.assertNotEqual(result["decision"], "ALLOW")

    def test_read_only_allow_and_live_denial_never_grant_effect(self):
        # Even PASS/ALLOW on a read-only LIVE query is not an execution receipt.
        for severity, command, approved in (
            ("P2", "OBSERVE", True),
            ("P1", "OBSERVE", True),
            ("P2", "REMEDIATE", False),
            ("P2", "REMEDIATE", True),
        ):
            with self.subTest(severity=severity, command=command, approved=approved):
                result = evaluate(decision(mode="LIVE", severity=severity,
                                           command=command, human_approved=approved))
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)

    def test_http_contract_remains_strict_and_internal_verdict_no_effect(self):
        with TestClient(app) as client:
            for mode, command, evidence_count in (
                ("DEMO", "REMEDIATE", 2),
                ("REPLAY", "EXECUTE", 0),
                ("STORY", "CANCEL", 2),
                ("LIVE", "OBSERVE", 2),
                ("LIVE", "REMEDIATE", 2),
            ):
                with self.subTest(mode=mode, command=command, evidence_count=evidence_count):
                    response = client.post("/api/policy/check", json=decision(
                        mode=mode, command=command, evidence_count=evidence_count).model_dump())
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(set(response.json()), {"state", "decision", "reason"})
                    self.assertIs(evaluate(decision(mode=mode, command=command,
                        evidence_count=evidence_count))["execution_allowed"], False)
                    self.assertIs(evaluate(decision(mode=mode, command=command,
                        evidence_count=evidence_count))["effect_allowed"], False)


if __name__ == "__main__":
    unittest.main()


# Shared Quality is architect-owned. Run the 9 synthetic fixture regressions
# alongside the 17 Policy safety cases without changing that workflow.
def load_tests(loader, tests, pattern):
    from test_policy_simulate_fixture import PolicySimulateFixtureTests
    tests.addTests(loader.loadTestsFromTestCase(PolicySimulateFixtureTests))
    return tests
