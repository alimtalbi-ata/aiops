import unittest
from datetime import datetime, timezone
from worker.fs147_action_binding import check_action_binding

class TestActionBinding(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 9, 6, tzinfo=timezone.utc)
        self.intent = dict(tenant_id="t1", run_id="r1", action_id="a1", target="fs-lab",
                           parameters_digest="a"*64, policy_revision="p1", dry_run=True)
        self.approval = {k: self.intent[k] for k in
                         ("tenant_id","run_id","action_id","target","parameters_digest","policy_revision")}
        self.approval.update(decision="APPROVED", authenticated=True, expires_at="2026-11-09T06:10:00Z")
    def check(self):
        return check_action_binding(self.intent, self.approval, now=self.now)
    def test_read_only_never_dispatch(self):
        self.assertEqual(self.check()["status"], "BOUND_READ_ONLY")
        self.assertFalse(self.check()["dispatch_allowed"])
    def test_cross_action_replay(self):
        for key, value in (("action_id","a2"),("target","other"),("run_id","r2"),
                           ("tenant_id","t2"),("parameters_digest","b"*64),("policy_revision","p2")):
            with self.subTest(key=key):
                self.intent[key] = value
                self.assertEqual(self.check()["reason"], "APPROVAL_MISMATCH")
                self.intent[key] = self.approval[key]
    def test_expiry_and_authentication(self):
        self.approval["expires_at"] = "2026-11-09T06:00:00Z"
        self.assertEqual(self.check()["reason"], "APPROVAL_EXPIRED")
        self.approval["expires_at"] = "2026-11-09T06:10:00Z"
        self.approval["authenticated"] = False
        self.assertEqual(self.check()["reason"], "AUTHENTICATION_UNVERIFIED")
    def test_refusal_and_live(self):
        self.approval["decision"] = "DENIED"
        self.assertEqual(self.check()["status"], "UNKNOWN")
        self.approval["decision"] = "APPROVED"
        self.intent["dry_run"] = False
        self.assertEqual(self.check()["reason"], "LIVE_OR_REFUSED")
    def test_bad_digest_and_missing(self):
        self.intent["parameters_digest"] = self.approval["parameters_digest"] = "z"*64
        self.assertEqual(self.check()["reason"], "INVALID_DIGEST")
        self.assertEqual(check_action_binding(None,self.approval,now=self.now)["status"], "UNKNOWN")
    def test_naive_clock(self):
        self.assertEqual(check_action_binding(self.intent,self.approval,now=datetime(2026,11,9))["reason"], "CLOCK_UNVERIFIED")
