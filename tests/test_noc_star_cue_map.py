import unittest
from demo.noc_star_cue_map import bind_noc_evidence_to_star,CUES
def index():
    names=("unified","synthetic","checkmk-export")
    return {"schema":"aiops-noc-evidence-index-v1",
            "counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,"live_remediation_authorized":False,
            "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,
                        "size_bytes":123,"class":"OFFLINE_TEST",
                        "source":"LOCAL_OFFLINE_BROWSER_RENDER",
                        "runtime_authenticated":False,"promotable_to_runtime":False} for n in names]}
class StarCueMapTests(unittest.TestCase):
    def test_all_cue_ids_are_known_and_not_event_bound(self):
        out=bind_noc_evidence_to_star(index())
        self.assertEqual(len(out["cues"]),9)
        self.assertEqual(set(out["cues"]),set(CUES))
        self.assertTrue(all(set(e["cue_ids"])<=set(CUES) and not e["event_bound"] for e in out["bindings"]))
        self.assertEqual(out["verified_event_links"],0)
        self.assertIsNone(out["run_id"])
    def test_reject_live_evidence_claim(self):
        data=index();data["entries"][0]["promotable_to_runtime"]=True
        with self.assertRaises(ValueError):bind_noc_evidence_to_star(data)
    def test_reject_unrecognized_filename(self):
        data=index();data["entries"][0]["file"]="other.png"
        with self.assertRaises(ValueError):bind_noc_evidence_to_star(data)
if __name__=="__main__":unittest.main()
