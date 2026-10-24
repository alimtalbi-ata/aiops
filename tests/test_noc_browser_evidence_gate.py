import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from demo.noc_browser_evidence_gate import verify_noc_offline_browser_evidence
NAMES=("unified.png","synthetic.png","checkmk-export.png")
class EvidenceGateTests(unittest.TestCase):
    def fixture(self,folder):
        rows=[]
        for n in NAMES:
            (folder/n).write_bytes(b"fake screenshot")
            rows.append({"file":n,"sha256":"a"*64,"size_bytes":123,
                         "evidence_type":"LOCAL_OFFLINE_BROWSER_RENDER","runtime_authenticated":False})
        obj={"schema":"aiops-noc-offline-browser-artifacts-v1","source":"SYNTHETIC_AND_UNVERIFIED_EXPORTS",
             "runtime_proof_count":0,"live_remediation_authorized":False,"captures":rows}
        (folder/"manifest.json").write_text(json.dumps(obj),encoding="utf-8")
        return obj
    def test_verification_returns_offline_only(self):
        with tempfile.TemporaryDirectory() as root,patch("demo.noc_browser_evidence_gate.inspect_png",return_value=("a"*64,123)):
            p=Path(root);self.fixture(p)
            result=verify_noc_offline_browser_evidence(p)
            self.assertEqual(result["evidence_class"],"OFFLINE_TEST")
            self.assertFalse(result["runtime_authenticated"])
    def test_tampered_digest_rejected(self):
        with tempfile.TemporaryDirectory() as root,patch("demo.noc_browser_evidence_gate.inspect_png",return_value=("b"*64,123)):
            p=Path(root);self.fixture(p)
            with self.assertRaises(ValueError):verify_noc_offline_browser_evidence(p)
    def test_fake_live_claim_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);obj=self.fixture(p);obj["runtime_proof_count"]=1
            (p/"manifest.json").write_text(json.dumps(obj),encoding="utf-8")
            with self.assertRaises(ValueError):verify_noc_offline_browser_evidence(p)
    def test_extra_file_rejected(self):
        with tempfile.TemporaryDirectory() as root,patch("demo.noc_browser_evidence_gate.inspect_png",return_value=("a"*64,123)):
            p=Path(root);self.fixture(p);(p/"surprise").write_text("x")
            with self.assertRaises(ValueError):verify_noc_offline_browser_evidence(p)
if __name__=="__main__":unittest.main()
