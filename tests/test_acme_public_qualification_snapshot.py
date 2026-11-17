"""Public qualification model is immutable-by-construction and always NO_GO."""
import unittest

from portal.acme_qualification_view import public_qualification_snapshot
from scripts.acme_autonomous_loop_qualification import STAGES
from scripts.acme_qualification_addon import SCENES


class PublicSnapshotTests(unittest.TestCase):
    def test_exact_stage_coverage_and_no_runtime_claims(self):
        result = public_qualification_snapshot()
        self.assertEqual([s[0] for s in result["stages"]], list(STAGES))
        self.assertEqual(len(result["scenes"]), len(SCENES))
        self.assertEqual(result["status"], "NO_GO")
        self.assertEqual(result["authority"], "STATIC_SOURCE_DECLARATION_ONLY")
        for key in ("runtime_e2e_verified", "viewer_acl_verified",
                    "browser_verified", "deployed_sha_attested",
                    "remediation_effect_verified", "learning_verified",
                    "autonomous_execution_allowed"):
            self.assertIs(result[key], False)
        self.assertEqual(result["stages"][-2][1], "NON VÉRIFIÉ")
        self.assertEqual(result["stages"][-1][1], "NON VÉRIFIÉ")
        self.assertEqual(result["scenes"][-2][1], "NON IMPLÉMENTÉ")

    def test_returned_rows_do_not_mutate_future_snapshots(self):
        a = public_qualification_snapshot()
        a["stages"][0][1] = "GO"
        a["scenes"][0][1] = "BROWSER VERIFIED"
        a["status"] = "GO"
        b = public_qualification_snapshot()
        self.assertEqual(b["status"], "NO_GO")
        self.assertNotEqual(b["stages"][0][1], "GO")
        self.assertNotEqual(b["scenes"][0][1], "BROWSER VERIFIED")


if __name__ == "__main__":
    unittest.main()
