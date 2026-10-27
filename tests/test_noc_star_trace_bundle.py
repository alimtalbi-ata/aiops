import unittest
from demo.noc_star_trace_bundle import make_synthetic_star_events,generate_star_trace_package
def index():
    names=("unified","synthetic","checkmk-export")
    return {"schema":"aiops-noc-evidence-index-v1",
            "counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,"live_remediation_authorized":False,
            "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,"size_bytes":123,
                        "class":"OFFLINE_TEST","source":"LOCAL_OFFLINE_BROWSER_RENDER",
                        "runtime_authenticated":False,"promotable_to_runtime":False} for n in names]}
class StarTraceBundleTests(unittest.TestCase):
    def test_repeatable_events(self):
        self.assertEqual(make_synthetic_star_events(),make_synthetic_star_events())
        self.assertEqual(len(make_synthetic_star_events()),9)
        self.assertEqual(len(set(r["event_id"] for r in make_synthetic_star_events())),9)
    def test_trace_and_hash_link(self):
        result,html=generate_star_trace_package(index())
        self.assertEqual(result["verified_runtime_event_links"],0)
        self.assertEqual(len(result["events"]),9)
        self.assertIn("RUN-ACME-OFFLINE-STAR",html)
    def test_reject_runtime_forgery(self):
        obj=index();obj["runtime_authenticated"]=True
        with self.assertRaises(ValueError):generate_star_trace_package(obj)
if __name__=="__main__":unittest.main()
