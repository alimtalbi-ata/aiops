import unittest
from demo.star_snapshot_choreography import CUES
from demo.star_scene_scripts import scene_plan

class ScenePlans(unittest.TestCase):
    def make(self, scenario):
        return {"schema":"star-portal-transport-v1","scenario":scenario,
                "safety":{"read_only":True,"runtime_authenticated":False,
                          "remediation_authorized":False},
                "frames":[{"step":x.cue,"application":x.service,"expected_view":x.view,
                           "capture_status":"missing","action_allowed":False,
                           "runtime_verified":False} for x in CUES]}
    def test_san_and_payments_have_nine_ordered_frames(self):
        for scenario in ("SAN_FABRIC_P1","PAYMENTS_P2"):
            with self.subTest(scenario=scenario):
                p=scene_plan(scenario,self.make(scenario))
                self.assertEqual(len(p["steps"]),9)
                self.assertFalse(p["runtime_qualified"])
                self.assertTrue(p["synthetic_scenario"])
                self.assertTrue(all(not x["action_allowed"] for x in p["steps"]))
    def test_mismatched_app_fails_closed(self):
        f=self.make("SAN_FABRIC_P1")
        f["frames"][0]["application"]="glpi"
        with self.assertRaises(ValueError):
            scene_plan("SAN_FABRIC_P1",f)
    def test_fake_runtime_claim_fails(self):
        f=self.make("PAYMENTS_P2")
        f["frames"][1]["runtime_verified"]=True
        with self.assertRaises(ValueError):
            scene_plan("PAYMENTS_P2",f)
    def test_identity_mismatch_fails(self):
        with self.assertRaises(ValueError):
            scene_plan("SAN_FABRIC_P1",self.make("PAYMENTS_P2"))

if __name__=="__main__":
    unittest.main()
