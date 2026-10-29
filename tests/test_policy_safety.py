import unittest

from fastapi.testclient import TestClient
from pydantic import ValidationError

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

    def test_synthetic_unsafe_critic_redundancy_or_confidence_never_passes(self):
        # DEMO remains a safe simulation, but an unqualified synthetic
        # assessment cannot be shown to the customer as a PASS gate.
        cases = (
            ({"critic_validated": False}, "critic"),
            ({"redundancy_ok": False}, "redundancy"),
            ({"confidence": 0.89}, "confidence"),
        )
        for mode in ("DEMO", "REPLAY", "STORY"):
            for changes, reason in cases:
                with self.subTest(mode=mode, changes=changes):
                    result = evaluate(decision(mode=mode, command="REMEDIATE",
                                               human_approved=True, **changes))
                    self.assertEqual((result["state"], result["decision"]),
                                     ("BLOCKED", "HUMAN_APPROVAL"))
                    self.assertIn(reason, result["reason"])
                    self.assertNotEqual(result["decision"], "ALLOW")

    def test_synthetic_valid_observation_still_simulates_without_live_effect(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                result = evaluate(decision(mode=mode, command="OBSERVE",
                                           human_approved=False, confidence=0.90))
                self.assertEqual((result["state"], result["decision"]),
                                 ("PASS", "SIMULATE"))


    def test_untyped_safety_assertions_are_rejected_before_evaluation(self):
        # Pydantic bool/number coercion previously accepted caller-supplied
        # strings such as "yes", "true" and "2" as positive proof.
        for field, invalid in (
            ("critic_validated", "yes"),
            ("critic_validated", 1),
            ("redundancy_ok", "true"),
            ("evidence_fresh", "true"),
            ("preconditions_verified", "yes"),
            ("fencing_verified", 1),
            ("human_approved", "true"),
            ("evidence_count", "2"),
            ("evidence_count", True),
            ("confidence", "0.99"),
            ("confidence", True),
        ):
            with self.subTest(field=field, invalid=invalid):
                payload = decision(mode="DEMO", command="REMEDIATE").model_dump()
                payload[field] = invalid
                with self.assertRaises(ValidationError):
                    Decision(**payload)

    def test_typed_synthetic_assertions_keep_simulation_only(self):
        result = evaluate(decision(mode="DEMO", command="REMEDIATE",
                                   confidence=1, evidence_count=1,
                                   critic_validated=True, redundancy_ok=True))
        self.assertEqual((result["state"], result["decision"]),
                         ("PASS", "SIMULATE"))

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


if __name__ == "__main__":
    unittest.main()
