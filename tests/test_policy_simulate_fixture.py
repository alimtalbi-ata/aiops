import unittest

from app.policy.main import Decision, evaluate
from app.policy.simulate_fixture import present_simulate_fixture


def decision(**changes):
    values = {
        "mode": "DEMO", "command": "REMEDIATE", "severity": "P2",
        "confidence": 0.99, "evidence_count": 2, "critic_validated": True,
        "redundancy_ok": True, "human_approved": True,
    }
    values.update(changes)
    return Decision(**values)


def fixture(**changes):
    params = {
        "timestamp": "2026-10-29T12:00:00+00:00",
        "fixture_actor_id": "approver-fixture",
    }
    params.update(changes)
    return present_simulate_fixture(decision(), **params)


class PolicySimulateFixtureTests(unittest.TestCase):
    def test_valid_canonical_utc_and_actor_keep_no_effect_contract(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            with self.subTest(mode=mode):
                result = present_simulate_fixture(decision(mode=mode),
                    timestamp="2026-10-29T12:00:00+00:00", fixture_actor_id="approver-fixture")
                self.assertEqual(result["policy"], evaluate(decision(mode=mode)))
                self.assertEqual(result["classification"], "SYNTHETIC_UNVERIFIED")
                self.assertEqual(result["provenance"], "WHAT_IF_FIXTURE_NOT_OBSERVED")
                self.assertTrue(result["dry_run"])
                self.assertIs(result["execution_allowed"], False)
                self.assertIs(result["effect_allowed"], False)
                self.assertIs(result["human"]["approval_valid_now"], False)
                self.assertIs(result["human"]["authenticated_runtime"], False)
                self.assertIs(result["audit"]["runtime_verified"], False)
                self.assertIsNone(result["audit"]["observed_at"])

    def test_live_and_unknown_modes_refused(self):
        with self.assertRaisesRegex(ValueError, "simulate_mode_required"):
            present_simulate_fixture(decision(mode="LIVE"),
                timestamp="2026-10-29T12:00:00+00:00", fixture_actor_id="approver-fixture")
        with self.assertRaisesRegex(ValueError, "policy_decision_required"):
            present_simulate_fixture({"mode": "DEMO"},
                timestamp="2026-10-29T12:00:00+00:00", fixture_actor_id="approver-fixture")

    def test_timestamp_must_be_canonical_utc(self):
        for timestamp in (
            "2026-10-29T12:00:00Z",
            "2026-10-29T12:00:00",
            "2026-10-29T13:00:00+01:00",
            "2026-10-29T12:00:00-00:00",
            "2026-10-29T12:00:00.1+00:00",
            "2026-10-29 12:00:00+00:00",
            "LIVE",
            "not-a-date",
            None, [], {}, 1,
        ):
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(ValueError, "gate_fixture_timestamp_invalid"):
                    fixture(timestamp=timestamp)

    def test_timestamp_accepts_builder_microsecond_precision(self):
        self.assertEqual(
            fixture(timestamp="2026-10-29T12:00:00.123456+00:00")["audit"]["fixture_timestamp"],
            "2026-10-29T12:00:00.123456+00:00",
        )

    def test_actor_must_be_safe_fixture_identifier(self):
        for actor in (None, "", "x" * 65, "with space", "operator/admin", "<script>",
                      "line\nbreak", "équipe", [], {}, 42, "approve\u2028me"):
            with self.subTest(actor=actor):
                with self.assertRaisesRegex(ValueError, "gate_fixture_actor_invalid"):
                    fixture(fixture_actor_id=actor)

    def test_actor_valid_boundaries(self):
        for actor in ("a", "a" * 64, "fixture.user_1:team-2"):
            with self.subTest(actor=actor):
                self.assertEqual(fixture(fixture_actor_id=actor)["human"]["fixture_actor_id"], actor)

    def test_no_policy_reason_or_decision_promotion(self):
        # The wrapper reuses the real Policy evaluator, not a caller-supplied
        # PASS/SIMULATE dictionary that could forge a reason.
        blocked = decision(evidence_count=0)
        self.assertEqual(evaluate(blocked)["decision"], "HUMAN_APPROVAL")
        with self.assertRaisesRegex(ValueError, "policy_not_simulate"):
            present_simulate_fixture(blocked,
                timestamp="2026-10-29T12:00:00+00:00", fixture_actor_id="approver-fixture")

    def test_human_approved_boolean_is_never_an_approval_receipt(self):
        for approved in (False, True):
            result = present_simulate_fixture(decision(human_approved=approved),
                timestamp="2026-10-29T12:00:00+00:00", fixture_actor_id="approver-fixture")
            self.assertEqual(result["policy"]["decision"], "SIMULATE")
            self.assertIs(result["human"]["approval_valid_now"], False)
            self.assertIs(result["execution_allowed"], False)


    def test_synthetic_actor_and_approval_boolean_never_grant_effect(self):
        for mode in ("DEMO", "REPLAY", "STORY"):
            for approved in (False, True):
                with self.subTest(mode=mode, approved=approved):
                    result = present_simulate_fixture(
                        decision(mode=mode, human_approved=approved),
                        timestamp="2026-10-29T12:00:00+00:00",
                        fixture_actor_id="SYNTHETIC_UNVERIFIED",
                    )
                    self.assertEqual(result["classification"], "SYNTHETIC_UNVERIFIED")
                    self.assertIs(result["execution_allowed"], False)
                    self.assertIs(result["effect_allowed"], False)
                    self.assertIs(result["human"]["approval_valid_now"], False)
                    self.assertIs(result["human"]["authenticated_runtime"], False)


if __name__ == "__main__":
    unittest.main()
