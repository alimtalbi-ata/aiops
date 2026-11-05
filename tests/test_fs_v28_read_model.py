import unittest
from app.core.fs_v28_read_model import project, INCIDENT, RUN, SCENARIO, EVIDENCE

RUN_RECORD = {"run_id": RUN, "incident_id": INCIDENT, "scenario_id": SCENARIO,
              "mode": "DEMO", "status": "CREATED"}
EVIDENCE_RECORD = {"evidence_id": EVIDENCE, "run_id": RUN, "incident_id": INCIDENT}
DENIAL = {"state": "DENY", "run_id": RUN, "incident_id": INCIDENT, "live_effects": False}


class FsV28ReadModelTests(unittest.TestCase):
    def test_created_does_not_start(self):
        result = project(RUN_RECORD, EVIDENCE_RECORD)
        self.assertEqual(result["status"], "CREATED")
        self.assertFalse(result["can_start"])
        self.assertFalse(result["can_resolve"])
        self.assertFalse(result["live_effects"])

    def test_wrong_evidence_correlation_fails_closed(self):
        result = project(RUN_RECORD, {**EVIDENCE_RECORD, "run_id": "RUN-OTHER"})
        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_wrong_incident_fails_closed(self):
        result = project({**RUN_RECORD, "incident_id": "INC-OTHER"}, EVIDENCE_RECORD)
        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_policy_refusal_is_terminal_without_effect(self):
        result = project({**RUN_RECORD, "status": "BLOCKED"}, EVIDENCE_RECORD, DENIAL)
        self.assertEqual(result["status"], "BLOCKED_NO_EFFECT")
        self.assertFalse(result["can_resolve"])

    def test_blocked_without_correlated_policy_is_unavailable(self):
        result = project({**RUN_RECORD, "status": "BLOCKED"}, EVIDENCE_RECORD)
        self.assertEqual(result["status"], "UNAVAILABLE")
        result = project({**RUN_RECORD, "status": "BLOCKED"}, EVIDENCE_RECORD,
                         {**DENIAL, "run_id": "RUN-OTHER"})
        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_resolved_does_not_claim_resolution(self):
        result = project({**RUN_RECORD, "status": "RESOLVED"}, EVIDENCE_RECORD)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertFalse(result["can_resolve"])

    def test_unknown_or_invalid_state_fails_closed(self):
        for state in ("RESOLVE", "SUCCESS", "RUNNING", "", None, True, 42):
            with self.subTest(state=state):
                result = project({**RUN_RECORD, "status": state}, EVIDENCE_RECORD)
                self.assertEqual(result["status"], "UNAVAILABLE")

    def test_known_observation_stages_are_non_authoritative(self):
        for state in ("OBSERVE", "ANALYST", "CRITIC", "POLICY"):
            with self.subTest(state=state):
                result = project({**RUN_RECORD, "status": state}, EVIDENCE_RECORD)
                self.assertEqual(result["status"], "IN_PROGRESS")
                self.assertFalse(result["can_start"])
                self.assertFalse(result["can_resolve"])

    def test_denial_requires_explicit_no_effect_attestation(self):
        for marker in (None, True, "false", 0):
            with self.subTest(marker=marker):
                denial = {**DENIAL, "live_effects": marker}
                result = project({**RUN_RECORD, "status": "BLOCKED"}, EVIDENCE_RECORD, denial)
                self.assertEqual(result["status"], "UNAVAILABLE")

    def test_live_mode_rejected(self):
        result = project({**RUN_RECORD, "mode": "LIVE"}, EVIDENCE_RECORD)
        self.assertEqual(result["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
