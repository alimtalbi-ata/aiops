import unittest
from scripts.acme_isolated_browser_receipt import qualify_local_browser_run

SHA = "a" * 40

class IsolatedBrowserReceiptTests(unittest.TestCase):
    def test_pass_is_ci_only_never_runtime(self):
        r = qualify_local_browser_run(source_sha=SHA, job_passed=True)
        self.assertEqual(r["status"], "PASS_CI_LOOPBACK_BROWSER_ONLY")
        self.assertEqual(r["viewports"], [375, 1440])
        for key in ("deployed_sha_attested", "runtime_e2e_verified",
                    "viewer_acl_verified", "remediation_effect_verified",
                    "learning_verified", "autonomous_execution_allowed"):
            self.assertIs(r[key], False)

    def test_failure_or_bad_sha_cannot_issue_receipt(self):
        for sha, passed in ((SHA, False), ("bad", True), (SHA.upper(), True),
                            (SHA, 1)):
            with self.subTest(sha=sha, passed=passed), self.assertRaises(ValueError):
                qualify_local_browser_run(source_sha=sha, job_passed=passed)
