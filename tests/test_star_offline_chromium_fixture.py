import tempfile
import unittest
from pathlib import Path
from demo.star_offline_chromium_fixture import validate_fixture_plan

def plan():
    return {"schema":"star-browser-capture-tasks-v1","browser_executed":False,
            "runtime_proof_count":0,"live_action_authorized":False,
            "tasks":[{"cue":"detect","capture_performed":False,"authenticated_runtime_proof":False}]}

class OfflineChromiumFixtureTests(unittest.TestCase):
    def test_valid_isolated_fixture(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/"detect.html").write_text("<h1>Synthetic</h1>")
            self.assertEqual(validate_fixture_plan(plan(),{"detect":"detect.html"},root)[0][0],"detect")
    def test_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                validate_fixture_plan(plan(),{"detect":"../private.html"},Path(td))
    def test_forged_runtime_state_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/"detect.html").write_text("<h1>Synthetic</h1>")
            p=plan();p["tasks"][0]["authenticated_runtime_proof"]=True
            with self.assertRaises(ValueError):
                validate_fixture_plan(p,{"detect":"detect.html"},root)
    def test_missing_fixture_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                validate_fixture_plan(plan(),{},Path(td))
    def test_unknown_cue_is_rejected_before_screenshot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"safe.html").write_text("<p>Fixture</p>",encoding="utf-8")
            p=plan()
            p["tasks"][0]["cue"]="../escape"
            with self.assertRaisesRegex(ValueError,"unknown or duplicate STAR cue"):
                validate_fixture_plan(p,{"../escape":"safe.html"},root)

    def test_reused_cue_is_rejected_before_screenshot(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"safe.html").write_text("<p>Fixture</p>",encoding="utf-8")
            p=plan()
            p["tasks"].append(dict(p["tasks"][0]))
            with self.assertRaisesRegex(ValueError,"unknown or duplicate STAR cue"):
                validate_fixture_plan(p,{"detect":"safe.html"},root)

if __name__=="__main__": unittest.main()
