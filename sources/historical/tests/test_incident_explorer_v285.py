"""V2.8.5 incident explorer regression tests, no service dependencies."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "app/portal/timeline_explain.py"
spec = importlib.util.spec_from_file_location("incident_explorer",path)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

RUNS=[
 {"run_id":"RUN-1","incident_id":"INC-A","status":"BLOCKED","mode":"DEMO"},
 {"run_id":"RUN-2","incident_id":"INC-A","status":"RESOLVED","mode":"DEMO"},
 {"run_id":"RUN-3","incident_id":"INC-B","status":"RUNNING","mode":"DEMO"},
]

class ExplorerTests(unittest.TestCase):
    def test_multiple_runs_group_under_incident(self):
        html=m.incident_explorer(RUNS,"RUN-1")
        self.assertEqual(html.count("<summary>"),2)
        self.assertIn("2 run(s)",html)
        self.assertIn("RUN-1",html)
        self.assertIn("RUN-2",html)

    def test_filter_status(self):
        html=m.incident_explorer(RUNS,"RUN-1",status_filter="BLOCKED")
        self.assertIn("RUN-1",html)
        self.assertNotIn("RUN-2",html)
        self.assertNotIn("RUN-3",html)

    def test_search_and_escape(self):
        html=m.incident_explorer(RUNS,"RUN-2",query="INC-A")
        self.assertNotIn("INC-B</strong>",html)
        malicious=m.incident_explorer(RUNS,"RUN-1",query='"><script>alert(1)</script>')
        self.assertNotIn("<script>",malicious)
        self.assertIn("&lt;script&gt;",malicious)

if __name__=="__main__":
    unittest.main()
