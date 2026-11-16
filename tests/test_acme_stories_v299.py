import importlib.util,unittest
from pathlib import Path
p=Path(__file__).resolve().parents[1]/"app/portal/acme_stories.py"
spec=importlib.util.spec_from_file_location("stories",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class StoryTests(unittest.TestCase):
    def test_six_distinct_industrial_cases(self):
        self.assertGreaterEqual(len(m.STORIES),6)
        self.assertEqual(len({s["id"] for s in m.STORIES}),len(m.STORIES))
    def test_claimed_maturity_explicit(self):
        self.assertTrue(all(s["status"] in ("TABLETOP_ONLY","HISTORICAL_DGX","BENCHMARK_ONLY") for s in m.STORIES))
        self.assertEqual(m.get_story("PAYROLL_FREEZE")["status"],"TABLETOP_ONLY")
    def test_story_has_customer_narrative(self):
        required=("persona","business_impact","service","symptom","hypothesis","control","outcome")
        self.assertTrue(all(all(s.get(k) for k in required) for s in m.STORIES))
if __name__=="__main__":unittest.main()
