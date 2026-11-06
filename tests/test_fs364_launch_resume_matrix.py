"""FS.364 launch/resume fail-closed matrix. Pure offline tests: no GLPI/Temporal I/O."""
import unittest
from app.core.fs364_correlation import launch_allowed, temporal_resume_allowed


class LaunchResumeMatrix(unittest.TestCase):
    def test_launch_requires_all_gates(self):
        valid = dict(mode="DEMO", authenticated=True, acl_ok=True,
                     stop_auto=False, policy_decision="ALLOW", human_approval=True)
        self.assertTrue(launch_allowed(**valid))
        refusals = dict(mode=["LIVE", "demo", None],
                        authenticated=[False, None, 1],
                        acl_ok=[False, None, 1],
                        stop_auto=[True, None, 0],
                        policy_decision=["DENY", "BLOCKED", None],
                        human_approval=[False, None, 1])
        for field, values in refusals.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertFalse(launch_allowed(**(valid | {field: value})))

    def test_temporal_resume_requires_all_gates(self):
        valid = dict(mode="DEMO", same_run=True, mode_match=True,
                     authenticated=True, acl_ok=True, stop_auto=False,
                     policy_decision="ALLOW", human_answer_verified=True,
                     approval_specific=True)
        self.assertTrue(temporal_resume_allowed(**valid))
        refusals = dict(mode=["LIVE", None],
                        same_run=[False, None, 1],
                        mode_match=[False, None, 1],
                        authenticated=[False, None, 1],
                        acl_ok=[False, None, 1],
                        stop_auto=[True, None, 0],
                        policy_decision=["DENY", "BLOCKED", None],
                        human_answer_verified=[False, None, 1],
                        approval_specific=[False, None, 1])
        for field, values in refusals.items():
            for value in values:
                with self.subTest(field=field, value=value):
                    self.assertFalse(temporal_resume_allowed(**(valid | {field: value})))


if __name__ == "__main__":
    unittest.main()
