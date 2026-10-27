import unittest
from demo.noc_evidence_center import render_noc_evidence_center
def sample():
    files=("unified","synthetic","checkmk-export")
    return {"schema":"aiops-noc-evidence-index-v1",
            "counts":{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0},
            "runtime_authenticated":False,"live_remediation_authorized":False,
            "entries":[{"id":"noc-offline-"+n,"file":n+".png","sha256":"a"*64,
                       "size_bytes":120,"class":"OFFLINE_TEST",
                       "source":"LOCAL_OFFLINE_BROWSER_RENDER",
                       "runtime_authenticated":False,"promotable_to_runtime":False} for n in files]}
class NocEvidenceCenterTests(unittest.TestCase):
    def test_renders_three_offline_proofs(self):
        result=render_noc_evidence_center(sample())
        self.assertIn("OFFLINE_TEST uniquement",result)
        self.assertIn("checkmk-export.png",result)
        self.assertIn("RUNTIME_EVIDENCE : 0",result)
    def test_live_promotion_rejected(self):
        obj=sample();obj["entries"][0]["promotable_to_runtime"]=True
        with self.assertRaises(ValueError):render_noc_evidence_center(obj)
    def test_fake_runtime_count_rejected(self):
        obj=sample();obj["counts"]["RUNTIME_EVIDENCE"]=1
        with self.assertRaises(ValueError):render_noc_evidence_center(obj)
    def test_invalid_filename_rejected(self):
        obj=sample();obj["entries"][0]["file"]="../../passwd"
        with self.assertRaises(ValueError):render_noc_evidence_center(obj)
if __name__=="__main__":unittest.main()
