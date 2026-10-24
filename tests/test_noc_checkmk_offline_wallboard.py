import unittest
from demo.noc_checkmk_offline_wallboard import render_checkmk_offline_noc
from demo.noc_checkmk_consolidation import consolidate_checkmk_snapshot

H={"schema":"aiops-checkmk-offline-readonly-v1","provenance":"OPERATOR_EXPORT_UNVERIFIED","runtime_authenticated":False,"live_remediation_authorized":False,"captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,"hosts":{"brocade-fc01":{"state":"OK","output":"up"}}}
S={"schema":"aiops-checkmk-services-loopback-v1","provenance":"LOOPBACK_UNVERIFIED","runtime_authenticated":False,"live_remediation_authorized":False,"captured_at":"2026-10-24T20:00:00Z","age_seconds":60.0,"services":[{"host":"brocade-fc01","description":"FC port","state":"CRIT","output":"down"}]}

class CheckmkOfflineWallboardTests(unittest.TestCase):
    def merged(self):return consolidate_checkmk_snapshot(H,S)
    def test_renders_host_and_service_status(self):
        page=render_checkmk_offline_noc(self.merged())
        self.assertIn("brocade-fc01",page)
        self.assertIn("FC port",page)
        self.assertIn("EXPORT HORS LIGNE NON AUTHENTIFIÉ",page)
        self.assertIn('data-state="CRIT"',page)
    def test_xss_safe_outputs(self):
        obj=self.merged()
        obj["hosts"]["brocade-fc01"]["services"][0]["output"]='<script>alert(1)</script>'
        page=render_checkmk_offline_noc(obj)
        self.assertIn("&lt;script&gt;",page)
        self.assertNotIn("<script>alert(1)</script>",page)
    def test_provenance_forgery_rejected(self):
        obj=self.merged();obj["runtime_authenticated"]=True
        with self.assertRaises(ValueError):render_checkmk_offline_noc(obj)
    def test_inconsistent_totals_rejected(self):
        obj=self.merged();obj["service_count"]=999
        with self.assertRaises(ValueError):render_checkmk_offline_noc(obj)

if __name__=="__main__":unittest.main()
