import json
import unittest
from pathlib import Path
from demo.noc_unified_offline import render_unified_noc
CAT=Path(__file__).resolve().parents[1]/"demo/rag_ops_fixture_catalog.json"
H={"schema":"aiops-checkmk-offline-readonly-v1","provenance":"OPERATOR_EXPORT_UNVERIFIED","runtime_authenticated":False,"live_remediation_authorized":False,"captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,"hosts":{"brocade-fc01":{"state":"OK","output":"up"}}}
S={"schema":"aiops-checkmk-services-loopback-v1","provenance":"LOOPBACK_UNVERIFIED","runtime_authenticated":False,"live_remediation_authorized":False,"captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,"services":[{"host":"brocade-fc01","description":"FC port","state":"CRIT","output":"down"}]}
class UnifiedNocTests(unittest.TestCase):
    def catalog(self):return json.loads(CAT.read_text(encoding="utf-8"))
    def test_separated_provenance_and_sandboxed_views(self):
        page=render_unified_noc(self.catalog(),H,S)
        self.assertIn("SYNTHÉTIQUE",page)
        self.assertIn("EXPORT NON AUTHENTIFIÉ",page)
        self.assertEqual(page.count('sandbox="allow-scripts"'),2)
        self.assertEqual(page.count("srcdoc="),2)
        self.assertNotIn("__SIM__",page)
        self.assertNotIn("__CHECK__",page)
        self.assertIn("&lt;!doctype html&gt;",page)
        self.assertIn("ACME Payments",page)
        self.assertIn("FC port",page)
        self.assertNotIn("allow-same-origin",page)
    def test_unverified_export_cannot_claim_runtime(self):
        with self.assertRaises(ValueError):
            render_unified_noc(self.catalog(),dict(H,runtime_authenticated=True),S)
    def test_untrusted_synthetic_doc_rejected(self):
        c=self.catalog();c["scenarios"][0]["source_type"]="VENDOR_OFFICIAL"
        with self.assertRaises(ValueError):render_unified_noc(c,H,S)
    def test_html_escape_source_value(self):
        s=dict(S,services=[dict(S["services"][0],output='<img src=x onerror=alert(1)>')])
        page=render_unified_noc(self.catalog(),H,s)
        self.assertNotIn('<img src=x onerror=alert(1)>',page)
        self.assertIn("&amp;lt;img",page)
if __name__=="__main__":unittest.main()
