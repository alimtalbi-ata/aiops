"""Projection tests: fake inputs cannot manufacture browser, effect or ACL proof."""
import copy
import unittest

from scripts.acme_autonomous_loop_qualification import assess_autonomous_loop
from scripts.acme_portal_route_inventory import SCENE_CANDIDATES
from scripts.acme_workbench_evidence_projection import project_workbench_evidence
from test_acme_core_worker_binding import pair


def evidence():
    loop = assess_autonomous_loop(*pair())
    readback = {
        "schema": "aiops.acme-readonly-runtime-recipe.v1",
        "status": "RUNTIME_READBACK_CONSISTENT_ONLY",
        "real_execution_allowed": False, "viewer_acl_verified": False,
        "browser_verified": False, "remediation_effect_verified": False,
        "autonomous_closed_loop_verified": False,
        "deployed_sha_attested": False, "learning_claim_verified": False,
    }
    routes = {
        "schema": "aiops.acme-portal-route-inventory.v1",
        "seven_scenes_browser_qualified": False, "live": "NO_GO",
        "scenes": [
            {"scene": scene, "browser_execution": "NOT_TESTED",
             "deployed_route": "NOT_VERIFIED", "selector": "NOT_VERIFIED",
             "status": "NOT_IMPLEMENTED" if scene == "itsm_worker"
                       else "SOURCE_ROUTE_CANDIDATE_ONLY"}
            for scene in SCENE_CANDIDATES
        ],
    }
    return loop, readback, routes


class WorkbenchProjectionTests(unittest.TestCase):
    def test_full_projection_never_promotes_to_go(self):
        result = project_workbench_evidence(*evidence())
        self.assertEqual(result["status"], "EVIDENCE_PROJECTION_ONLY")
        self.assertEqual(result["readback"], "SUPPLIED_READBACK_CONSISTENT_ONLY")
        self.assertEqual(result["scenes"]["itsm_worker"], "NOT_IMPLEMENTED")
        self.assertEqual(result["stages"]["LEARN"], "NOT_VERIFIED")
        self.assertEqual(result["stages"]["REMEDIATION_EFFECT"], "NOT_VERIFIED")
        self.assertFalse(result["autonomous_execution_allowed"])
        self.assertEqual(result["viewer_acl"], "NOT_VERIFIED")

    def test_missing_evidence_fails_closed(self):
        self.assertEqual(project_workbench_evidence(None, None, None)["status"], "NO_GO")

    def test_fake_browser_pass_rejected(self):
        loop, readback, routes = evidence()
        routes["seven_scenes_browser_qualified"] = True
        self.assertEqual(project_workbench_evidence(loop, readback, routes)["status"], "NO_GO")

    def test_fake_effect_or_learning_rejected(self):
        for field in ("remediation_effect_verified", "learning_claim_verified",
                      "viewer_acl_verified", "deployed_sha_attested"):
            loop, readback, routes = evidence()
            readback[field] = True
            self.assertEqual(project_workbench_evidence(loop, readback, routes)["status"], "NO_GO")

    def test_fake_stage_or_scene_rejected(self):
        loop, readback, routes = evidence()
        loop["stages"]["REMEDIATION_EFFECT"] = "OFFLINE_DECLARED_ONLY"
        self.assertEqual(project_workbench_evidence(loop, readback, routes)["status"], "NO_GO")
        loop, readback, routes = evidence()
        routes["scenes"][0]["browser_execution"] = "PASS"
        self.assertEqual(project_workbench_evidence(loop, readback, routes)["status"], "NO_GO")

    def test_duplicate_scene_rejected(self):
        loop, readback, routes = evidence()
        routes["scenes"][1]["scene"] = routes["scenes"][0]["scene"]
        self.assertEqual(project_workbench_evidence(loop, readback, routes)["status"], "NO_GO")


if __name__ == "__main__":
    unittest.main()
