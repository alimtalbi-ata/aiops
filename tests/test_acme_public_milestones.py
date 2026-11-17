import unittest
from portal.acme_milestones import public_milestone_contract

EXPECTED_IDS = ("identity_acl", "deployed_provenance", "core_twin_join",
                "seven_scenes", "remediation_verify", "audit_learn")


class PublicMilestonesTests(unittest.TestCase):
    def test_six_ordered_milestones_never_grant_runtime_authority(self):
        contract = public_milestone_contract()
        self.assertEqual(contract["schema"], "aiops.acme-public-milestones.v1")
        self.assertEqual(contract["status"], "NO_GO")
        self.assertEqual(contract["authority"], "STATIC_SOURCE_DECLARATION_ONLY")
        self.assertEqual(tuple(x["id"] for x in contract["milestones"]), EXPECTED_IDS)
        self.assertEqual(contract["milestones"][0]["status"], "BLOCKED")
        self.assertTrue(all(x["required_proof"] for x in contract["milestones"]))
        self.assertTrue(all(x["status"] in ("BLOCKED", "NOT_VERIFIED")
                            for x in contract["milestones"]))
        for key in ("runtime_e2e_verified", "viewer_acl_verified",
                    "deployed_sha_attested", "remediation_effect_verified",
                    "learning_verified", "autonomous_execution_allowed"):
            self.assertIs(contract[key], False)

    def test_caller_cannot_mutate_next_response(self):
        first = public_milestone_contract()
        first["status"] = "GO"
        first["milestones"][0]["status"] = "VERIFIED"
        first["milestones"].clear()
        second = public_milestone_contract()
        self.assertEqual(second["status"], "NO_GO")
        self.assertEqual(len(second["milestones"]), 6)
        self.assertEqual(second["milestones"][0]["status"], "BLOCKED")
