"""V2.8.7: recorded per-event evidence and AI objections, safely escaped."""
import importlib.util
from pathlib import Path
import unittest
p=Path(__file__).resolve().parents[1]/"app/portal/timeline_explain.py"
spec=importlib.util.spec_from_file_location("timeline_287",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class EventDetailsTests(unittest.TestCase):
    def test_analyst_and_critic_details(self):
        event={"stage":"DGX_CRITIC","event_type":"CRITIC_COMPLETED",
               "status":"BLOCKED","decision":"HUMAN_APPROVAL",
               "evidence_ids":["E-1"],"confidence":.65,
               "payload":{"critique":{"validated":False,"final_recommendation":"HUMAN_APPROVAL",
                         "issues":[{"code":"CAUSAL_LEAP","description":"Not proven"}]}}}
        html=m.event_box(event,6)
        for value in ("Box #6","E-1","0.65","HUMAN_APPROVAL","CAUSAL_LEAP","Not proven"):
            self.assertIn(value,html)
    def test_error_and_html_escaped(self):
        html=m.event_box({"stage":"DGX_ANALYST","event_type":"STAGE_FAILED",
                          "status":"FAILED","payload":{"error":"<script>alert(1)</script>",
                          "analysis":{"severity":"UNKNOWN","confidence":.2,
                          "hypotheses":[{"statement":"<img src=x>",
                                         "supporting_evidence_ids":["E1"]}]}}},2)
        self.assertIn("&lt;script&gt;",html)
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img",html)
        self.assertIn("UNKNOWN",html)
    def test_missing_details_not_fabricated(self):
        self.assertIn("Aucune donnée détaillée",m.event_box({"stage":"NORMALIZE"},1))
if __name__=="__main__":
    unittest.main()
