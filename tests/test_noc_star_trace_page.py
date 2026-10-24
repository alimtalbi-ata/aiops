import unittest
from demo.noc_star_trace_page import render_noc_star_trace
from demo.noc_star_cue_map import CUES
def index():
    names=("unified","synthetic","checkmk-export")
    return {"schema":"aiops-noc-evidence-index-v1","counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,"live_remediation_authorized":False,
            "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,"size_bytes":123,
                        "class":"OFFLINE_TEST","source":"LOCAL_OFFLINE_BROWSER_RENDER",
                        "runtime_authenticated":False,"promotable_to_runtime":False} for n in names]}
def events():
    return [{"cue":cue,"run_id":"RUN-DEMO","incident_id":"INC-DEMO","event_id":"EV-"+str(i),
             "source_type":"SYNTHETIC","payload":{"step":i}} for i,cue in enumerate(CUES)]
class StarTraceTests(unittest.TestCase):
    def test_all_steps_and_provenance(self):
        page=render_noc_star_trace(index(),events())
        self.assertIn("OFFLINE_TEST",page)
        self.assertIn("RUN-DEMO",page)
        self.assertEqual(page.count("<tr><td>"),12)
        self.assertIn("ILLUSTRATIVE_SYNTHETIC_HASH_BINDING",page)
    def test_xss_escaped(self):
        rows=events();rows[0]["payload"]["log"]="<script>attack</script>"
        page=render_noc_star_trace(index(),rows)
        self.assertNotIn("<script>attack</script>",page)
    def test_cross_run_rejected(self):
        rows=events();rows[0]["run_id"]="OTHER"
        with self.assertRaises(ValueError):render_noc_star_trace(index(),rows)
if __name__=="__main__":unittest.main()
