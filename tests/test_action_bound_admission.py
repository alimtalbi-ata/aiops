"""Offline contract tests: no network, GLPI, PostgreSQL, or Temporal writes."""
import copy
import unittest

from app.core.action_bound_admission import admit_resume


def fixture(mode="DEMO"):
    i = dict(tenant_id="t1", incident_id="i1", run_id="r1",
             action_id="a1", action_digest="sha256:abc",
             fencing_token="f1", fencing_epoch=2, mode=mode,
             live_preflight_verified=(mode == "LIVE"),
             policy_decision_id="pol-1")
    b = {k: i[k] for k in ("tenant_id", "incident_id", "run_id", "action_id", "action_digest")}
    return (i, dict(b, decision="ALLOW", mode=mode, decision_id="pol-1"),
            dict(b, decision="APPROVED", mode=mode, policy_decision_id="pol-1",
                 approval_id="hitl-1", approver_id="operator-1",\n                 revoked=False, consumed=False),
            dict(b, fencing_token="f1", fencing_epoch=2, active=True),
            dict(b, fencing_token="f1", fencing_epoch=2,
                 state="WAITING_APPROVAL", resume_requested=False))


class TestActionBoundAdmission(unittest.TestCase):
    def test_demo_and_nonmutation(self):
        args = fixture()
        before = copy.deepcopy(args)
        self.assertEqual(admit_resume(*args).state, "ELIGIBLE")
        self.assertEqual(args, before)

    def test_live_preflight_unknown(self):
        args = fixture("LIVE")
        args[0]["live_preflight_verified"] = None
        self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")

    def test_every_authority_bound_to_action(self):
        for pos in (1, 2, 3, 4):
            for key in ("tenant_id", "incident_id", "run_id", "action_id", "action_digest"):
                with self.subTest(pos=pos, key=key):
                    args = fixture()
                    args[pos][key] = "foreign"
                    self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")

    def test_cross_incident_replay_is_not_eligible(self):
        for pos in (1, 2, 3, 4):
            with self.subTest(authority=pos):
                args = fixture()
                args[pos]["incident_id"] = "another-incident"
                self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")
        for pos in (1, 2, 3, 4):
            with self.subTest(authority=pos):
                args = fixture()
                args[pos].pop("incident_id")
                self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")

    def test_policy_denial(self):
        for decision in ("DENY", None, "UNKNOWN"):
            args = fixture()
            args[1]["decision"] = decision
            self.assertEqual(admit_resume(*args).state, "DENIED")

    def test_fencing_and_temporal_replay(self):
        for pos, key, value in ((3, "fencing_epoch", 1),
                                (3, "active", False),
                                (4, "fencing_token", "stale"),
                                (4, "resume_requested", True),
                                (4, "state", "RUNNING")):
            with self.subTest(pos=pos, key=key):
                args = fixture()
                args[pos][key] = value
                self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")

    def test_native_hitl_policy_decision_binding(self):
        for pos, key, value in (
            (0, "policy_decision_id", "pol-other"),
            (0, "policy_decision_id", None),
            (1, "decision_id", "pol-other"),
            (1, "decision_id", ""),
            (2, "policy_decision_id", "pol-other"),
            (2, "approval_id", None),
            (2, "approval_id", ""),
            (2, "approver_id", None),
            (2, "approver_id", " "),
        ):
            with self.subTest(pos=pos, key=key, value=value):
                args = fixture()
                args[pos][key] = value
                self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")

    def test_native_hitl_lifecycle_fail_closed(self):
        for field in ("revoked", "consumed"):
            for value in (None, True, 0, "", "false"):
                with self.subTest(field=field, value=value):
                    args = fixture()
                    args[2][field] = value
                    self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")
            args = fixture()
            del args[2][field]
            self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")

    def test_bool_epoch_rejected(self):
        args = fixture()
        args[0]["fencing_epoch"] = True
        self.assertEqual(admit_resume(*args).state, "NEEDS_HUMAN")


if __name__ == "__main__":
    unittest.main()
