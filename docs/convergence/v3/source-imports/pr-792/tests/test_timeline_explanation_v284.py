"""Timeline V2.8.4: selectable real Core runs, escaped labels, explainable step boxes."""
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/"app/portal/timeline_explain.py"
spec=importlib.util.spec_from_file_location("timeline_explain_test",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class TimelineTests(unittest.TestCase):
    def test_select_success_failure_and_active_runs(self):
        html=m.run_selector([
            {"run_id":"RUN-PASS","status":"RESOLVED","mode":"DEMO"},
            {"run_id":"RUN-BLOCK","status":"BLOCKED","mode":"DEMO"},
            {"run_id":"RUN-FAIL","status":"FAILED","mode":"DEMO"},
            {"run_id":"RUN-ACTIVE","status":"RUNNING","mode":"DEMO"}], "RUN-BLOCK")
        for label in ["RESOLVED","BLOCKED","FAILED","RUNNING","aria-current"]:
            self.assertIn(label,html)

    def test_critic_block_has_factual_reason_not_guessed(self):
        html=m.event_box({"stage":"DGX_CRITIC","event_type":"CRITIC_COMPLETED",
                          "status":"BLOCKED","decision":"HUMAN_APPROVAL","occurred_at":"2026-10-21"},8)
        self.assertIn("Box #8",html)
        self.assertIn("HUMAN_APPROVAL",html)
        self.assertIn("Voir ses objections",html)

    def test_escape_untrusted_event_content(self):
        html=m.event_box({"stage":"<script>","event_type":"<img src=x>","status":"FAILED"},1)
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img",html)
        self.assertIn("&lt;script&gt;",html)

if __name__=="__main__":
    unittest.main()
