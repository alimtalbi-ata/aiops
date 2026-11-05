import unittest
from app.core.fs_v28_transition_guard import validate

INCIDENT = "INC-DEMO-FS-001"
RUN = "RUN-4FABD1786F107E51"
EVIDENCE = "EVD-D2069BA816126499"


def event(stage, index, **extra):
    return {"event_id": f"evt-{index}", "incident_id": INCIDENT, "run_id": RUN,
            "evidence_id": EVIDENCE, "mode": "DEMO", "live_effects": False,
            "stage": stage, **extra}


def check(events):
    return validate(events, incident_id=INCIDENT, run_id=RUN, evidence_id=EVIDENCE)


class TransitionGuardTests(unittest.TestCase):
    def test_created_is_inert(self):
        self.assertEqual(check([])["status"], "CREATED")

    def test_ordered_observation_is_non_authoritative(self):
        seq = [event("OBSERVE", 1), event("ANALYST", 2), event("CRITIC", 3)]
        self.assertEqual(check(seq)["status"], "IN_PROGRESS")
        self.assertFalse(check(seq)["can_resolve"])

    def test_policy_denial_is_terminal(self):
        seq = [event("OBSERVE", 1), event("ANALYST", 2), event("CRITIC", 3),
               event("POLICY", 4, decision="DENY")]
        self.assertEqual(check(seq)["status"], "BLOCKED_NO_EFFECT")
        self.assertEqual(check(seq + [dict(seq[-1])])["status"], "BLOCKED_NO_EFFECT")
        self.assertEqual(check(seq + [event("RESOLVE", 5)])["status"], "UNAVAILABLE")

    def test_fail_closed_gaps_and_positive_policy(self):
        for seq in ([event("ANALYST", 1)],
                    [event("OBSERVE", 1), event("POLICY", 2, decision="DENY")],
                    [event("OBSERVE", 1), event("ANALYST", 2), event("CRITIC", 3),
                     event("POLICY", 4, decision="ALLOW")]):
            with self.subTest(seq=seq):
                self.assertEqual(check(seq)["status"], "UNAVAILABLE")

    def test_conflicting_replay_or_wrong_correlation_fails(self):
        first = event("OBSERVE", 1)
        self.assertEqual(check([first, {**first, "stage": "ANALYST"}])["status"], "UNAVAILABLE")
        self.assertEqual(check([{**first, "run_id": "RUN-OTHER"}])["status"], "UNAVAILABLE")
        self.assertEqual(check([{**first, "evidence_id": "EVD-OTHER"}])["status"], "UNAVAILABLE")
        self.assertEqual(check([{**first, "live_effects": True}])["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
