"""V28 DEMO negative contract matrix: no dispatch, no LIVE, no synthetic approval."""
import unittest

from app.core.fs_v28_transition_guard import validate
from app.core.fs_v28_read_model import project

INC = "INC-DEMO-FS-001"
RUN = "RUN-4FABD1786F107E51"
EVD = "EVD-D2069BA816126499"


def ev(stage, n, **overrides):
    record = {"event_id": f"fs-v28-{n}", "incident_id": INC, "run_id": RUN,
              "evidence_id": EVD, "mode": "DEMO", "live_effects": False, "stage": stage}
    record.update(overrides)
    return record


def check(events):
    return validate(events, incident_id=INC, run_id=RUN, evidence_id=EVD)


class V28SafetyMatrix(unittest.TestCase):
    def setUp(self):
        self.prefix = [ev("OBSERVE", 1), ev("ANALYST", 2), ev("CRITIC", 3)]
        self.denied = self.prefix + [ev("POLICY", 4, decision="DENY")]

    def test_denied_is_terminal_and_identical_replay_is_idempotent(self):
        self.assertEqual(check(self.denied)["status"], "BLOCKED_NO_EFFECT")
        self.assertEqual(check(self.denied + [dict(self.denied[0]), dict(self.denied[3])])["status"],
                         "BLOCKED_NO_EFFECT")
        for result in (check(self.denied), check(self.denied + [dict(self.denied[3])])):
            self.assertFalse(result["can_start"])
            self.assertFalse(result["can_resolve"])
            self.assertFalse(result["live_effects"])

    def test_no_new_event_after_policy_denial(self):
        for stage in ("OBSERVE", "ANALYST", "CRITIC", "POLICY", "RESOLVE"):
            with self.subTest(stage=stage):
                self.assertEqual(check(self.denied + [ev(stage, 5)])["status"], "UNAVAILABLE")

    def test_no_policy_allow_or_missing_predecessors(self):
        for events in ([ev("POLICY", 1, decision="DENY")],
                       self.prefix[:1] + [ev("CRITIC", 3)],
                       self.prefix + [ev("POLICY", 4, decision="ALLOW")],
                       self.prefix + [ev("POLICY", 4)]):
            with self.subTest(events=events):
                self.assertEqual(check(events)["status"], "UNAVAILABLE")

    def test_conflicting_retry_never_accepted(self):
        for changed in ({"stage": "RESOLVE"}, {"decision": "ALLOW"},
                        {"run_id": "RUN-OTHER"}, {"live_effects": True}):
            with self.subTest(changed=changed):
                conflicting = dict(self.denied[-1], **changed)
                self.assertEqual(check(self.denied + [conflicting])["status"], "UNAVAILABLE")

    def test_reject_untrusted_correlation_and_live_effect_flags(self):
        for field, bad in (("incident_id", "INC-OTHER"), ("run_id", "RUN-OTHER"),
                           ("evidence_id", "EVD-OTHER"), ("mode", "LIVE"),
                           ("live_effects", 0), ("live_effects", None),
                           ("event_id", ""), ("event_id", None)):
            with self.subTest(field=field, bad=bad):
                self.assertEqual(check([ev("OBSERVE", 1, **{field: bad})])["status"],
                                 "UNAVAILABLE")

    def test_resolved_is_never_inferred_from_evidence(self):
        run = {"run_id": RUN, "incident_id": INC, "scenario_id": "FS-DEBIAN-SYNTHETIC",
               "mode": "DEMO", "status": "RESOLVED"}
        evidence = {"evidence_id": EVD, "run_id": RUN, "incident_id": INC}
        self.assertEqual(project(run, evidence)["status"], "UNAVAILABLE")
        self.assertFalse(project(run, evidence)["can_resolve"])


if __name__ == "__main__":
    unittest.main()
