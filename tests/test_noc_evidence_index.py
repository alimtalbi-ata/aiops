import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from demo.noc_evidence_index import build_noc_evidence_index
NAMES=("unified.png","synthetic.png","checkmk-export.png")
class NocEvidenceIndexTests(unittest.TestCase):
    def setup(self,path):
        entries=[]
        for name in NAMES:
            (path/name).write_bytes(b"test")
            entries.append({"file":name,"sha256":"a"*64,"size_bytes":123,
                            "evidence_type":"LOCAL_OFFLINE_BROWSER_RENDER","runtime_authenticated":False})
        data={"schema":"aiops-noc-offline-browser-artifacts-v1","source":"SYNTHETIC_AND_UNVERIFIED_EXPORTS",
              "runtime_proof_count":0,"live_remediation_authorized":False,"captures":entries}
        (path/"manifest.json").write_text(json.dumps(data),encoding="utf-8")
    def test_three_offline_entries_no_runtime(self):
        with tempfile.TemporaryDirectory() as temp,patch("demo.noc_browser_evidence_gate.inspect_png",return_value=("a"*64,123)):
            folder=Path(temp);self.setup(folder)
            output=build_noc_evidence_index(folder)
            self.assertEqual(output["counts"],{"OFFLINE_TEST":3,"OBSERVATION":0,"RUNTIME_EVIDENCE":0})
            self.assertTrue(all(not a["promotable_to_runtime"] for a in output["entries"]))
    def test_tampered_capture_rejected(self):
        with tempfile.TemporaryDirectory() as temp,patch("demo.noc_browser_evidence_gate.inspect_png",return_value=("b"*64,123)):
            folder=Path(temp);self.setup(folder)
            with self.assertRaises(ValueError):build_noc_evidence_index(folder)
if __name__=="__main__":unittest.main()
