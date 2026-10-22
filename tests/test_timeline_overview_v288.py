import importlib.util
import unittest
from pathlib import Path
from datetime import datetime, timezone

p=Path(__file__).resolve().parents[1]/"app/portal/timeline_explain.py"
spec=importlib.util.spec_from_file_location("timeline_288",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class InvestigationTests(unittest.TestCase):
    def test_old_running_warns_without_state_rewrite(self):
        run={"incident_id":"INC-1","status":"RUNNING","mode":"DEMO",
             "started_at":"2026-10-21T10:00:00+00:00"}
        events=[{"stage":"DGX_CRITIC","status":"BLOCKED","event_type":"CRITIC_COMPLETED"}]
        output=m.investigation_overview(run,events,
              [{"incident_id":"INC-1","title":"Payments","severity":"P1"}],
              now=datetime(2026,10,21,12,0,tzinfo=timezone.utc))
        self.assertIn("plus de 30 minutes",output)
        self.assertIn("RUNNING",output)
        self.assertIn("Payments",output)
        self.assertIn('href="#event-1"',output)

    def test_event_anchor_and_escaped_incident_title(self):
        output=m.event_box({"stage":"NORMALIZE","status":"PASS"},3)
        self.assertIn('id="event-3"',output)
        summary=m.investigation_overview(
            {"status":"RESOLVED","incident_id":"INC-X"},[],
            [{"incident_id":"INC-X","title":"<script>","severity":"P2"}])
        self.assertIn("&lt;script&gt;",summary)
        self.assertNotIn("<script>",summary)
        self.assertNotIn("plus de 30 minutes",summary)

if __name__=="__main__":
    unittest.main()
