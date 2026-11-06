import sqlite3
import unittest

from app.core.fs364_correlation import (
    Link, ContractRefused, bind, launch_allowed, temporal_resume_allowed
)

BASE = Link("alert-fs147", "INC-FS147", "RUN-FS147", "EVD-FS147", 147, "DEMO")

class FS364ContractTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def put(self, link=BASE, **kwargs):
        return bind(self.db, link, verified_ticket=True, authenticated=True, **kwargs)

    def test_insert_and_identical_replay(self):
        self.assertEqual(self.put(), BASE)
        self.assertEqual(self.put(), BASE)
        self.assertEqual(self.db.execute("SELECT count(*) FROM fs364_links").fetchone()[0], 1)

    def test_conflicting_replay_and_cross_run_rejected(self):
        self.put()
        for changed in (
            Link(BASE.fingerprint, BASE.incident_id, "RUN-OTHER", BASE.evidence_id, 147, "DEMO"),
            Link("different", BASE.incident_id, BASE.run_id, BASE.evidence_id, 147, "DEMO"),
            Link(BASE.fingerprint, BASE.incident_id, BASE.run_id, BASE.evidence_id, 147, "LIVE"),
            Link("new", "new-incident", "new-run", BASE.evidence_id, 147, "DEMO"),
        ):
            with self.subTest(changed=changed), self.assertRaises(ContractRefused):
                self.put(changed)
        self.assertEqual(self.db.execute("SELECT count(*) FROM fs364_links").fetchone()[0], 1)

    def test_wrong_ticket_and_missing_identity_fail_closed(self):
        for link in (Link("f","i","r","e",146,"DEMO"),
                     Link("f","i","r","e",147,"INVALID"),
                     Link("","i","r","e",147,"DEMO")):
            with self.assertRaises(ContractRefused):
                self.put(link)

    def test_glpi_unavailable_or_unauthenticated(self):
        for kwargs in ({"verified_ticket":False,"authenticated":True},
                       {"verified_ticket":True,"authenticated":False},
                       {"verified_ticket":True,"authenticated":True,"stop_auto":False}):
            with self.assertRaises(ContractRefused):
                bind(self.db, BASE, **kwargs)

    def test_launch_never_automatic_or_policy_refused(self):
        args = dict(mode="DEMO", authenticated=True, acl_ok=True,
                    stop_auto=True, policy_decision="ALLOW", human_approval=True)
        self.assertFalse(launch_allowed(**args))
        args["stop_auto"] = False
        args["policy_decision"] = "BLOCKED"
        self.assertFalse(launch_allowed(**args))
        args["policy_decision"] = "ALLOW"
        args["human_approval"] = False
        self.assertFalse(launch_allowed(**args))

    def test_live_launch_rejected_even_if_all_other_gates_true(self):
        self.assertFalse(launch_allowed(
            mode="LIVE", authenticated=True, acl_ok=True,
            stop_auto=False, policy_decision="ALLOW", human_approval=True
        ))

    def test_temporal_resume_requires_all_independent_gates(self):
        args = dict(mode="DEMO", same_run=True, mode_match=True, authenticated=True, acl_ok=True,
                    stop_auto=False, policy_decision="ALLOW",
                    human_answer_verified=True, approval_specific=True)
        self.assertTrue(temporal_resume_allowed(**args))
        for key, bad in (("mode","LIVE"),("same_run",False),("mode_match",False),
                         ("authenticated",False),("acl_ok",False),
                         ("stop_auto",True),("policy_decision","BLOCKED"),
                         ("human_answer_verified",False),("approval_specific",False)):
            with self.subTest(key=key):
                self.assertFalse(temporal_resume_allowed(**{**args,key:bad}))

    def test_truthy_strings_never_count_as_verified_authorization(self):
        for field in ("verified_ticket", "authenticated", "stop_auto"):
            args = dict(verified_ticket=True, authenticated=True, stop_auto=True)
            args[field] = "true"
            with self.subTest(bind_field=field), self.assertRaises(ContractRefused):
                bind(self.db, BASE, **args)
        launch = dict(mode="DEMO", authenticated=True, acl_ok=True,
                      stop_auto=False, policy_decision="ALLOW", human_approval=True)
        for field in ("authenticated", "acl_ok", "human_approval"):
            with self.subTest(launch_field=field):
                self.assertFalse(launch_allowed(**{**launch, field: "true"}))
        self.assertFalse(launch_allowed(**{**launch, "stop_auto": ""}))
        resume = dict(mode="DEMO", same_run=True, mode_match=True,
                      authenticated=True, acl_ok=True, stop_auto=False,
                      policy_decision="ALLOW", human_answer_verified=True,
                      approval_specific=True)
        for field in ("same_run", "mode_match", "authenticated", "acl_ok",
                      "human_answer_verified", "approval_specific"):
            with self.subTest(resume_field=field):
                self.assertFalse(temporal_resume_allowed(**{**resume, field: "true"}))
        self.assertFalse(temporal_resume_allowed(**{**resume, "stop_auto": ""}))

if __name__ == "__main__":
    unittest.main()
