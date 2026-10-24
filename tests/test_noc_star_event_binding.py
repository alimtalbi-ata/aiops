import unittest
from demo.noc_star_event_binding import bind_synthetic_star_events
from demo.noc_star_cue_map import CUES
def index():
    names=("unified","synthetic","checkmk-export")
    return {"schema":"aiops-noc-evidence-index-v1","counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,"live_remediation_authorized":False,
            "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,"size_bytes":123,"class":"OFFLINE_TEST",
                        "source":"LOCAL_OFFLINE_BROWSER_RENDER","runtime_authenticated":False,
                        "promotable_to_runtime":False} for n in names]}
def events():
    return [{"cue":cue,"run_id":"RUN-DEMO","incident_id":"INC-DEMO","event_id":"EV-"+str(i),
             "source_type":"SYNTHETIC","payload":{"step":i}} for i,cue in enumerate(CUES)]
class SyntheticStarBindingTests(unittest.TestCase):
    def test_nine_events_bound_without_runtime_claim(self):
        result=bind_synthetic_star_events(index(),events())
        self.assertEqual(len(result["events"]),9)
        self.assertEqual(result["verified_runtime_event_links"],0)
        self.assertEqual(len(result["captures"]),3)
        self.assertTrue(all(len(x["event_sha256"])==64 for x in result["events"]))
    def test_mixed_incidents_rejected(self):
        rows=events();rows[3]["incident_id"]="INC-OTHER"
        with self.assertRaises(ValueError):bind_synthetic_star_events(index(),rows)
    def test_forged_source_rejected(self):
        rows=events();rows[1]["source_type"]="REAL"
        with self.assertRaises(ValueError):bind_synthetic_star_events(index(),rows)
    def test_reordered_cues_rejected(self):
        rows=events();rows[1],rows[2]=rows[2],rows[1]
        with self.assertRaises(ValueError):bind_synthetic_star_events(index(),rows)
if __name__=="__main__":unittest.main()
