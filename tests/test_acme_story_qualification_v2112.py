import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"tools/qualify_acme_story_v2112.py"
spec=importlib.util.spec_from_file_location("storycheck",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
source=(Path(__file__).resolve().parents[1]/"app/portal/main.py").read_text()
class StoryQualification(unittest.TestCase):
    def test_controls_and_sequence(self):
        result=m.inspect_story(source)
        self.assertTrue(result["passed"],result)
        self.assertEqual(result["steps"],10)
    def test_missing_js_handler_fails(self):
        self.assertFalse(m.inspect_story(source.replace('pos=-1;paint()','pos=-1'))["passed"])
    def test_explicit_simulation_label_required(self):
        self.assertFalse(m.inspect_story(source.replace("FICTIF / SANS EFFET","LIVE")).get("passed"))
if __name__=="__main__":unittest.main()
