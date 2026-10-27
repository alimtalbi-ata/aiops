import unittest
from demo.star_snapshot_choreography import CUES
from demo.star_portal_storyboard import storyboard

class PortalStoryboardTests(unittest.TestCase):
    def report(self):
        return {"schema":"star-capture-evidence-v1",
                "entries":[{"cue": c.cue, "status":"missing"} for c in CUES],
                "runtime_authenticated":False,"business_validated":False,
                "human_approval_authenticated":False,"live_action_authorized":False}

    def test_nine_frames_never_authorize_actions(self):
        result=storyboard(self.report(),"SAN_FABRIC_P1")
        self.assertEqual(len(result["frames"]),9)
        self.assertTrue(all(not x["action_allowed"] for x in result["frames"]))

    def test_fake_pictures_are_labeled(self):
        r=self.report()
        r["entries"][0]["status"]="simulated"
        result=storyboard(r,"PAYMENTS_P2")
        self.assertIn("fictive",result["frames"][0]["caption"])

    def test_out_of_order_rejected(self):
        r=self.report()
        r["entries"][0],r["entries"][1]=r["entries"][1],r["entries"][0]
        with self.assertRaises(ValueError):
            storyboard(r,"SAN_FABRIC_P1")

    def test_claimed_authority_rejected(self):
        r=self.report()
        r["business_validated"]=True
        with self.assertRaises(ValueError):
            storyboard(r,"SAN_FABRIC_P1")

    def test_unknown_state_rejected(self):
        r=self.report()
        r["entries"][0]["status"]="real_verified"
        with self.assertRaises(ValueError):
            storyboard(r,"PAYMENTS_P2")

if __name__=="__main__":
    unittest.main()
