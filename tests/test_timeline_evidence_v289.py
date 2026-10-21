import importlib.util
import unittest
from pathlib import Path

p=Path(__file__).resolve().parents[1]/"app/portal/timeline_explain.py"
spec=importlib.util.spec_from_file_location("timeline_289",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class EvidenceCatalogTests(unittest.TestCase):
    def test_provenance_source_and_timestamps(self):
        html=m.evidence_catalog([{"evidence_id":"EVD-1","source":"demo-observe",
          "claim":"FC errors increased","observed_at":"2026-10-21T12:00:00Z",
          "known_at":"2026-10-21T12:01:00Z","confidence":0.85,
          "payload_hash":"abcdef","provenance":{"synthetic":True}}])
        for value in ('id="proof-EVD-1"',"FC errors increased","demo-observe","abcdef","synthetic"):
            self.assertIn(value,html)
    def test_xss_and_missing_data(self):
        self.assertIn("Aucune preuve",m.evidence_catalog([]))
        html=m.evidence_catalog([{"evidence_id":"EVD-2","source":"<script>alert(1)</script>",
                                  "claim":"<img src=x>","provenance":{"unsafe":"<b>"}}])
        self.assertNotIn("<script>",html)
        self.assertNotIn("<img",html)
        self.assertIn("&lt;script&gt;",html)
if __name__=="__main__":
    unittest.main()
