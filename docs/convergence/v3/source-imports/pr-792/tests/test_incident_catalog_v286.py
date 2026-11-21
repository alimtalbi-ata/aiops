"""V2.8.6 regression: incidents with no workflow remain visible."""
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/"app/portal/timeline_explain.py"
spec=importlib.util.spec_from_file_location("timeline_v286",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class IncidentCatalogTests(unittest.TestCase):
    def test_incident_without_run_is_visible(self):
        html=m.incident_explorer(
            [{"incident_id":"INC-A","run_id":"RUN-1","status":"BLOCKED"}],
            "RUN-1", incidents=[
                {"incident_id":"INC-A","title":"Known case","severity":"P1"},
                {"incident_id":"INC-B","title":"No workflow","severity":"P2"}
            ])
        self.assertIn("No workflow",html)
        self.assertIn("Aucun run enregistré",html)
        self.assertIn("RUN-1",html)

    def test_no_run_filter_and_escaped_title(self):
        html=m.incident_explorer([],None,status_filter="NO_RUN",incidents=[
            {"incident_id":"INC-ONLY","title":"<script>alert(1)</script>","severity":"P2"}
        ])
        self.assertIn("INC-ONLY",html)
        self.assertNotIn("<script>",html)
        self.assertIn("&lt;script&gt;",html)

if __name__=="__main__":
    unittest.main()
